import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import anthropic
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    transform_schema,
)
from anthropic.types import Message, MessageParam, OutputConfigParam, TextBlock
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from tenacity import RetryCallState, retry, retry_if_exception_type, wait_exponential

_MAX_TOKENS = 5000
_DEFAULT_PROMPT_VERSION = "v0.1"
_DEFAULT_AI_MODEL = "claude-haiku-4-5-20251001"

logger = logging.getLogger(__name__)
_ROOT_DIR = Path(__file__).resolve().parents[4]
_DOTENV_PATH = _ROOT_DIR / "backend" / ".env"


class LLMStopReasonError(RuntimeError):
    """Base error for Anthropic responses that stop before valid output is returned."""


class LLMMaxTokensError(LLMStopReasonError):
    """Raised when Anthropic stops because the response reached max_tokens."""


class LLMToolUseError(LLMStopReasonError):
    """Raised when Anthropic requests tool use that this adapter cannot handle."""


class LLMPauseTurnError(LLMStopReasonError):
    """Raised when Anthropic pauses a turn that this adapter cannot resume."""


class LLMRefusalError(LLMStopReasonError):
    """Raised when Anthropic refuses the request for safety reasons."""


class LLMContextWindowExceededError(LLMStopReasonError):
    """Raised when Anthropic reports that the model context window was exceeded."""


class LLMTokenBudgetExceededError(LLMStopReasonError):
    """Raised when continuation attempts exceed the adapter token budget."""


def _stop_after_attempts_by_error(retry_state: RetryCallState) -> bool:
    """Dynamically drops or extends retry limits based on the specific exception."""
    if retry_state.outcome is None:
        return retry_state.attempt_number >= 2

    exc = retry_state.outcome.exception()

    if isinstance(exc, APIStatusError):
        if (
            exc.status_code in {408, 429} or exc.status_code >= 500
        ):  # request_timeout, rate_limited, transient_provider (500), transient_timeout (504), transient_overload (529)
            return retry_state.attempt_number >= 6

        elif exc.status_code in {
            400,
            401,
            402,
            403,
            404,
            413,
            422,
        }:  # invalid_request_error, authentication_error, billing_error, permission_error, not_found_error, request_too_large, unprocessable_entity
            return retry_state.attempt_number >= 1

        else:  # 409 (ConflictError), etc.
            return retry_state.attempt_number >= 2

    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return retry_state.attempt_number >= 6

    # 3. Default fallback for other retryable errors
    return retry_state.attempt_number >= 1


@retry(
    stop=_stop_after_attempts_by_error,  # Dynamically change the max attempts based on the exception type
    wait=wait_exponential(multiplier=1, min=2, max=32),  # Wait 2s, 4s, 8s, 16s...
    retry=retry_if_exception_type(
        (
            APIConnectionError,
            APITimeoutError,
            APIStatusError,
        )
    ),
    reraise=True,  # Throw original exception if all fail
)
def call_model[
    T: BaseModel
](
    system_context: str,
    user_message: str,
    *,
    response_model: type[T],
    ai_model: str = _DEFAULT_AI_MODEL,
    prompt_version: str = _DEFAULT_PROMPT_VERSION,
    case_info: str = "",
) -> T:
    """Call Anthropic and parse the response into a Pydantic model.

    Args:
        system_context: System prompt that defines model behavior.
        user_message: User prompt containing the task input.
        response_model: Pydantic model class used to validate the response.
        ai_model: Anthropic model name to call.
        prompt_version: Version label for the prompt used.
        case_info: Optional case identifier used in failure logs.

    Returns:
        The validated structured response.

    Raises:
        TypeError: If response_model is not a Pydantic model class.
        ValidationError: If the model output cannot be parsed into the response
            model even after a retry.
        json.JSONDecodeError: If the model returns invalid JSON that cannot be
            recovered.
    """
    if not isinstance(response_model, type) or not issubclass(
        response_model, BaseModel
    ):
        raise TypeError(
            "Type for calling structured model is not a Pydantic BaseModel: "
            f"{response_model}"
        )

    logger.debug(f"system_context: {system_context}")
    logger.debug(f"user_message: {user_message}")

    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

    client = anthropic.Anthropic()
    remaining_tokens = (
        _MAX_TOKENS  # start a counter to make sure we don't use too many tokens
    )
    schema = _convert_base_model_to_json_schema(response_model)
    messages: list[MessageParam] = [
        {
            "role": "user",
            "content": user_message,
        }
    ]
    output_config: OutputConfigParam = {
        "format": {"type": "json_schema", "schema": schema},
    }
    added_context = ""
    response: Message | None = None
    output: T | None
    structured_output: T

    while True:
        if remaining_tokens < 0:
            raise LLMTokenBudgetExceededError(
                f"Claude exceeded the max_tokens limit of {_MAX_TOKENS}."
            )

        try:
            response = client.messages.create(
                model=ai_model,
                max_tokens=remaining_tokens,
                system=system_context,
                messages=messages,
                output_config=output_config,
            )
            remaining_tokens -= response.usage.output_tokens

            output = _convert_response_to_structured_output(
                response=response,
                response_model=response_model,
                messages=messages,
                user_message=user_message,
                system_context=system_context,
            )
            if output is not None:
                structured_output = output
                break

        except (json.JSONDecodeError, ValidationError) as exc:
            if response is None:
                raise
            added_context = _raise_or_modify_message_for_format_exception(
                exc,
                system_context=system_context,
                user_message=user_message,
                added_context=added_context,
                response_model=response_model,
                ai_model=ai_model,
                case_info=case_info,
                response=response,
                messages=messages,
            )

    logger.info(
        f"Timestamp: {datetime.now()}, "
        f"model: {ai_model}, prompt version: {prompt_version}"
    )
    logger.debug(f"response: {_parse_message_to_string(response)}")

    return structured_output


def _convert_response_to_structured_output[
    T: BaseModel
](
    *,
    response: Message,
    response_model: type[T],
    messages: list[MessageParam],
    user_message: str,
    system_context: str,
) -> (T | None):
    if response.stop_reason == "end_turn" and response.content:
        return _convert_response_to_model_type(response, response_model)

    if response.stop_reason == "end_turn" and not response.content:
        # Add a continuation prompt in a NEW user message
        messages.append({"role": "user", "content": "Please continue"})

        return None

    elif response.stop_reason == "max_tokens":
        raise LLMMaxTokensError(
            f"Reached max tokens {_MAX_TOKENS}.  Raise token limits or shorten user message and/or system context.  Exiting"
        )

    elif response.stop_reason == "tool_use":
        raise LLMToolUseError("Tool use not yet implemented.")

    # Continue the conversation after Anthropic pauses a long-running turn.
    elif response.stop_reason == "pause_turn":
        raise LLMPauseTurnError("pause_turn returned; continuation not implemented")

    elif response.stop_reason == "refusal":
        raise LLMRefusalError(
            f"Claude was unable to process this request due to safety concerns.  System context = {system_context}, \nuser message = {user_message}."
        )

    elif response.stop_reason == "model_context_window_exceeded":
        raise LLMContextWindowExceededError(
            f"Claude reached the model context window limit.  Reduce tokens in system context and/or user message.  System context = {system_context}, \nuser message = {user_message}."
        )

    return None  # just in case catch-all that shouldn't occur


def _raise_or_modify_message_for_format_exception[
    T: BaseModel
](
    exc: ValidationError | json.JSONDecodeError,
    *,
    system_context: str,
    user_message: str,
    added_context: str,
    response_model: type[T],
    ai_model: str,
    case_info: str,
    response: Message,
    messages: list[MessageParam],
) -> str:
    logger.warning(
        _create_error_message(
            case_info=case_info,
            ai_model=ai_model,
            system_context=system_context,
            user_message=user_message,
            response=_parse_message_to_string(response),
        )
    )
    if isinstance(exc, ValidationError):
        _log_validation_error_messages(exc)

    # only allow one retry for response format errors
    if added_context:
        raise exc

    added_context = (
        "Your previous response did not match the required schema. I got "
        f"{exc.__class__.__name__}: {exc}. Return only valid structured output matching "
        f"{response_model} in json format. Original message:"
    )
    messages.append({"role": "user", "content": added_context + user_message})

    return added_context


def _convert_base_model_to_json_schema(model_class: type[BaseModel]) -> dict[str, Any]:
    """Generate an Anthropic-compatible JSON schema from a Pydantic model."""
    schema = model_class.model_json_schema()
    return transform_schema(schema)


def _convert_response_to_model_type[
    T: BaseModel
](response: Message, response_model: type[T]) -> T:
    """Parse a model response into a validated Pydantic object."""
    raw_text = _extract_text_from_response(response)
    if "```json" in raw_text:
        clean_text = (
            raw_text.strip().removeprefix("```json").removesuffix("```").strip()
        )
    else:
        clean_text = raw_text
    data_dict = json.loads(clean_text)
    return response_model.model_validate(data_dict)


def _extract_text_from_response(response: Message) -> str:
    """Return the first text block from a model response."""
    if response.content and isinstance(response.content[0], TextBlock):
        return response.content[0].text
    else:
        raise ValueError("LLM response does not contain text.")


def _create_error_message(
    *,
    case_info: str,
    ai_model: str,
    system_context: str,
    user_message: str,
    response: str,
) -> str:
    """Build a detailed log message for a failed model response."""
    return (
        f"Model failed for case: {case_info}, model={ai_model}"
        f" max_tokens={_MAX_TOKENS}, system={system_context},"
        f" \nand user_message={user_message}\nresponse: {response}"
    )


def _parse_message_to_string(response: Message | None) -> str:
    """Return the first response text block as a string, or an empty string."""
    return (
        response.content[0].text
        if (
            response and response.content and isinstance(response.content[0], TextBlock)
        )
        else ""
    )


def _log_validation_error_messages(err: ValidationError) -> None:
    """Log each individual field-level validation error from a ValidationError."""
    for error in err.errors():
        logger.debug(
            f"Error type: {error['type']}\n"
            f"Location:   {error['loc']}\n"
            f"Faulty data: {error['input']}"
        )
