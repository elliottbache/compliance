"""Shared LLM adapter errors and structured-output repair helpers."""

import json
import logging

from pydantic import BaseModel, ValidationError

from compliance.config import settings

logger = logging.getLogger(__name__)


class LLMStopReasonError(RuntimeError):
    """Base error for LLM responses that stop before valid output is returned."""


class LLMToolUseError(LLMStopReasonError):
    """Raised when requests tool use that this adapter cannot handle."""


class LLMMaxTokensError(LLMStopReasonError):
    """Raised when the LLM stops because the response reached max_tokens."""


class LLMTokenBudgetExceededError(LLMStopReasonError):
    """Raised when continuation attempts exceed the adapter token budget."""


def raise_or_create_format_repair_prompt[
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
    response_text: str,
    max_tokens: int,
) -> str:
    """Log invalid structured output and return one schema-repair prompt.

    The helper intentionally returns plain text instead of mutating provider
    message objects so Anthropic and Ollama adapters can rebuild their own
    provider-specific message lists.
    """
    logger.warning(
        _create_error_message(
            case_info=case_info,
            ai_model=ai_model,
            system_context=system_context,
            user_message=user_message,
            response=response_text,
            max_tokens=max_tokens,
        )
    )
    if isinstance(exc, ValidationError):
        _log_validation_error_messages(exc)

    # only allow one retry for response format errors
    if added_context:
        raise exc

    return (
        "Your previous response did not match the required schema. I got "
        f"{exc.__class__.__name__}: {exc}. Return only valid structured output matching "
        f"{response_model} in json format. Original message:"
    )


def _create_error_message(
    *,
    case_info: str,
    ai_model: str,
    system_context: str,
    user_message: str,
    response: str,
    max_tokens: int,
) -> str:
    """Build a detailed log message for a failed model response."""
    system_context = system_context if settings.ai_log_prompts else "[redacted]"
    user_message = user_message if settings.ai_log_prompts else "[redacted]"
    return (
        f"Model failed for case: {case_info}, model={ai_model}"
        f" max_tokens={max_tokens}, system={system_context},"
        f" \nand user_message={user_message}\nresponse: {response}"
    )


def _log_validation_error_messages(err: ValidationError) -> None:
    """Log each individual field-level validation error from a ValidationError."""
    for error in err.errors():
        logger.debug(
            f"Error type: {error['type']}\n"
            f"Location:   {error['loc']}\n"
            f"Faulty data: {error['input']}"
        )
