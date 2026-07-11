"""Ollama/Qwen structured-output adapter with retry and schema repair handling."""

import json
import logging

import httpx
import ollama
from ollama import ChatResponse
from pydantic import BaseModel, ValidationError
from tenacity import RetryCallState, retry, retry_if_exception_type, wait_exponential

from compliance.config import settings
from compliance.llm._helpers import (
    LLMMaxTokensError,
    LLMStopReasonError,
    LLMTokenBudgetExceededError,
    LLMToolUseError,
    raise_or_create_format_repair_prompt,
)

logger = logging.getLogger(__name__)

_MAX_TOKENS = settings.ollama_num_ctx
_DEFAULT_AI_MODEL = "qwen3:4b"
_DEFAULT_PROMPT_VERSION = "v0.1"


class LLMEmptyResponseError(LLMStopReasonError):
    """Raised when Ollama stops without returning response content."""


def _stop_after_attempts_by_error(retry_state: RetryCallState) -> bool:
    """Dynamically drops or extends retry limits based on the specific exception."""
    if retry_state.outcome is None:
        return retry_state.attempt_number >= 2

    exc = retry_state.outcome.exception()
    if isinstance(exc, (httpx.TransportError, ConnectionRefusedError)):
        return retry_state.attempt_number >= 6

    if not isinstance(exc, ollama.ResponseError):
        return retry_state.attempt_number >= 1

    status_code = exc.status_code or 0

    if (
        status_code in {408, 429} or status_code >= 500
    ):  # request_timeout, rate_limited, transient_provider (500), transient_timeout (504), transient_overload (529)
        return retry_state.attempt_number >= 6

    elif status_code in {
        400,
        401,
        402,
        403,
        404,
        413,
        422,
    }:  # invalid_request_error, authentication_error, billing_error, permission_error, not_found_error, request_too_large, unprocessable_entity
        return retry_state.attempt_number >= 1

    elif status_code == 409:  # 409 (ConflictError)
        return retry_state.attempt_number >= 2

    # Default fallback for other retryable errors
    return retry_state.attempt_number >= 1


class QwenAIProvider:
    """Structured-output provider backed by an Ollama chat model."""

    @retry(
        stop=_stop_after_attempts_by_error,  # Dynamically change the max attempts based on the exception type
        wait=wait_exponential(multiplier=1, min=2, max=32),  # Wait 2s, 4s, 8s, 16s...
        retry=retry_if_exception_type(
            (ollama.ResponseError, httpx.TransportError, ConnectionRefusedError)
        ),
        reraise=True,  # Throw original exception if all fail
    )
    def call_model[
        T: BaseModel
    ](
        self,
        system_context: str,
        user_message: str,
        *,
        response_model: type[T],
        ai_model: str = _DEFAULT_AI_MODEL,
        prompt_version: str = _DEFAULT_PROMPT_VERSION,
        case_info: str = "",
    ) -> T:
        """Call Ollama and parse the response into a Pydantic model.

        Args:
            system_context: System prompt that defines model behavior.
            user_message: User prompt containing the task input.
            response_model: Pydantic model class used to validate the response.
            ai_model: Ollama model name to call.
            prompt_version: Version label for the prompt used.
            case_info: Optional case identifier used in failure logs.

        Returns:
            The validated structured response.

        Raises:
            TypeError: If response_model is not a Pydantic model class.
            LLMEmptyResponseError: If Ollama stops with empty content twice.
            LLMMaxTokensError: If Ollama truncates the response.
            ValidationError: If the model output cannot be parsed into the response
                model even after a schema-repair retry.
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

        local_system_context = system_context + "\nReturn the output as json."
        if settings.ai_log_prompts:
            logger.debug(f"system_context: {local_system_context}")
            logger.debug(f"user_message: {user_message}")
        else:
            logger.debug("AI prompt logging is disabled.")

        messages = _create_messages(local_system_context, user_message)
        remaining_tokens = (
            _MAX_TOKENS  # start a counter to make sure we don't use too many tokens
        )
        added_context = ""
        retried_empty_response = False
        response = None
        client = ollama.Client(
            host=settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
        )

        while True:
            if remaining_tokens < 0:
                raise LLMTokenBudgetExceededError(
                    f"Ollama exceeded the max_tokens limit of {_MAX_TOKENS}."
                )

            try:
                response = client.chat(
                    model=ai_model,
                    messages=messages,
                    # Ollama parses the Pydantic schema automatically
                    format=response_model.model_json_schema(),
                    options={
                        "num_ctx": settings.ollama_num_ctx,  # Sets the context window to 8,192 tokens
                        "temperature": settings.ollama_temperature,
                    },
                )

                output = _convert_response_to_structured_output(
                    response=response,
                    response_model=response_model,
                    user_message=user_message,
                    system_context=system_context,
                )
                if output is None:
                    if retried_empty_response:
                        raise LLMEmptyResponseError(
                            "Ollama returned done_reason='stop' with empty content "
                            "after one fresh retry."
                        )

                    retried_empty_response = True
                    messages = _create_messages(local_system_context, user_message)
                    continue

                structured_output = output
                break

            except ollama.ResponseError as exc:
                if "out of memory" in exc.error.lower() or "cuda" in exc.error.lower():
                    logger.exception(
                        "Ollama reported an out-of-memory or CUDA failure."
                    )
                elif exc.status_code == 500:
                    logger.exception("Ollama returned an internal server error.")
                else:
                    logger.exception("Ollama returned a response error.")
                raise

            except httpx.ReadTimeout:
                logger.exception(
                    "Timed out waiting for Ollama at %s.", settings.ollama_base_url
                )
                raise

            except (httpx.TransportError, ConnectionRefusedError):
                logger.exception(
                    "Could not connect to Ollama at %s.", settings.ollama_base_url
                )
                raise

            except (json.JSONDecodeError, ValidationError) as exc:
                if (
                    not response
                    or not response.get("message")
                    or not response["message"].get("content")
                ):
                    raise

                response_text = response["message"]["content"]

                added_context = raise_or_create_format_repair_prompt(
                    exc,
                    system_context=system_context,
                    user_message=user_message,
                    added_context=added_context,
                    response_model=response_model,
                    ai_model=ai_model,
                    case_info=case_info,
                    response_text=response_text,
                    max_tokens=settings.ollama_num_ctx,
                )
                messages = _create_messages(
                    local_system_context, added_context + user_message
                )

            except LLMStopReasonError:
                raise

            except Exception:
                logger.exception("Unexpected error while calling Ollama.")
                raise

        return structured_output


def _create_messages(system_context: str, user_message: str) -> list[dict[str, str]]:
    """Create a fresh Ollama chat message list."""
    return [
        {"role": "system", "content": system_context},
        {"role": "user", "content": user_message},
    ]


def _create_qwen_max_tokens_error(
    *,
    system_context: str,
    user_message: str,
) -> LLMMaxTokensError:
    """Build the max-token error with prompt redaction settings applied."""
    if settings.ai_log_prompts:
        exc_system_context = system_context
        exc_user_message = user_message
    else:
        exc_system_context = ""
        exc_user_message = ""

    return LLMMaxTokensError(
        f"Ollama truncated the output due to length limits. "
        f"System context = {exc_system_context}, \nuser message = {exc_user_message}."
    )


def _convert_response_to_structured_output[
    T: BaseModel
](
    *,
    response: ChatResponse,
    response_model: type[T],
    user_message: str,
    system_context: str,
) -> (T | None):
    """Handle Ollama stop reasons and return validated output when available."""
    done_reason = response.get("done_reason")
    message_obj = response.get("message", {})
    content = message_obj.get("content", "")

    if message_obj.get("tool_calls"):
        raise LLMToolUseError("Tool use not yet implemented.")

    if done_reason == "stop" and not content:
        return None

    if done_reason == "stop":
        return response_model.model_validate_json(content)

    elif done_reason == "length":
        raise _create_qwen_max_tokens_error(
            system_context=system_context,
            user_message=user_message,
        )

    raise LLMStopReasonError(f"Unexpected Ollama done_reason: {done_reason!r}.")
