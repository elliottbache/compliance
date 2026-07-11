from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from compliance.llm.qwen_api import (
    LLMEmptyResponseError,
    LLMMaxTokensError,
    LLMToolUseError,
    QwenAIProvider,
    _convert_response_to_structured_output,
    _stop_after_attempts_by_error,
)
from ollama import ChatResponse
from pydantic import BaseModel


class ExampleModel(BaseModel):
    value: int


def _retry_state(attempt_number: int, exception: BaseException | None):
    outcome = None
    if exception is not None:
        outcome = SimpleNamespace(exception=lambda: exception)

    return SimpleNamespace(attempt_number=attempt_number, outcome=outcome)


def _chat_response(*, content: str = "", done_reason: str = "stop") -> ChatResponse:
    return ChatResponse(
        done_reason=done_reason,
        message={"role": "assistant", "content": content},
    )


class TestConvertResponseToStructuredOutput:
    def test_returns_validated_model_for_stop_response(self) -> None:
        response = _chat_response(content='{"value": 7}')

        result = _convert_response_to_structured_output(
            response=response,
            response_model=ExampleModel,
            user_message="user text",
            system_context="system text",
        )

        assert result == ExampleModel(value=7)

    def test_returns_none_for_empty_stop_response(self) -> None:
        response = _chat_response(content="")

        result = _convert_response_to_structured_output(
            response=response,
            response_model=ExampleModel,
            user_message="user text",
            system_context="system text",
        )

        assert result is None

    def test_raises_max_tokens_error_for_length_response(self) -> None:
        response = _chat_response(content='{"value": 7}', done_reason="length")

        with pytest.raises(LLMMaxTokensError, match="truncated"):
            _convert_response_to_structured_output(
                response=response,
                response_model=ExampleModel,
                user_message="user text",
                system_context="system text",
            )

    def test_raises_tool_use_error_for_tool_calls(self) -> None:
        response = ChatResponse(
            done_reason="stop",
            message={
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "lookup", "arguments": {}}}],
            },
        )

        with pytest.raises(LLMToolUseError, match="Tool use"):
            _convert_response_to_structured_output(
                response=response,
                response_model=ExampleModel,
                user_message="user text",
                system_context="system text",
            )


class TestQwenErrors:
    def test_empty_response_error_describes_ollama_stop(self) -> None:
        error = LLMEmptyResponseError("Ollama returned empty content.")

        assert "empty content" in str(error)


class TestStopAfterAttemptsByError:
    def test_read_timeout_stops_after_six_attempts(self) -> None:
        error = httpx.ReadTimeout("Ollama timed out.")

        assert _stop_after_attempts_by_error(_retry_state(5, error)) is False
        assert _stop_after_attempts_by_error(_retry_state(6, error)) is True


class TestCallModel:
    def test_logs_and_reraises_unexpected_errors(self) -> None:
        client = MagicMock()
        client.chat.side_effect = RuntimeError("boom")

        with (
            patch("compliance.llm.qwen_api.ollama.Client", return_value=client),
            patch("compliance.llm.qwen_api.logger.exception") as mock_exception,
            pytest.raises(RuntimeError, match="boom"),
        ):
            QwenAIProvider().call_model(
                "system text",
                "user text",
                response_model=ExampleModel,
                ai_model="qwen-test",
            )

        mock_exception.assert_called_once_with("Unexpected error while calling Ollama.")
