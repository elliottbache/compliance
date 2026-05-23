import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import compliance.llm.anthropic_api as anthropic_api
import httpx
import pytest
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)
from anthropic.types import TextBlock
from compliance.llm.anthropic_api import (
    _call_model,
    _convert_base_model_to_json_schema,
    _convert_response_to_model_type,
    _create_error_message,
    _extract_text_from_response,
    _log_validation_error_messages,
    _parse_message_to_string,
    call_structured_model,
    dynamic_stop_by_error,
)
from pydantic import BaseModel, ValidationError
from tenacity import wait_none


@pytest.fixture
def text_block_factory():
    def _build(text: str) -> TextBlock:
        return TextBlock.model_validate({"type": "text", "text": text})

    return _build


@pytest.fixture
def response_factory(text_block_factory):
    def _build(text: str):
        return SimpleNamespace(content=[text_block_factory(text)])

    return _build


class ExampleModel(BaseModel):
    value: int


def _anthropic_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _anthropic_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code=status_code, request=_anthropic_request())


def _retry_state(attempt_number: int, exception: BaseException | None):
    outcome = None
    if exception is not None:
        outcome = SimpleNamespace(exception=lambda: exception)

    return SimpleNamespace(attempt_number=attempt_number, outcome=outcome)


def _api_connection_error() -> APIConnectionError:
    return APIConnectionError(request=_anthropic_request())


def _api_timeout_error() -> APITimeoutError:
    return APITimeoutError(request=_anthropic_request())


def _api_status_error(status_code: int) -> APIStatusError:
    return APIStatusError(
        f"Status {status_code}",
        response=_anthropic_response(status_code),
        body={"error": {"message": f"status {status_code}"}},
    )


def _model_response(
    *,
    stop_reason: str = "end_turn",
    content: list | None = None,
    total_tokens: int = 10,
):
    if content is None:
        content = [TextBlock(type="text", text='{"value": 7}')]

    return SimpleNamespace(
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(total_tokens=total_tokens),
    )


class TestCallStructuredModel:
    def test_returns_validated_model(self) -> None:
        response = SimpleNamespace(
            content=[TextBlock(type="text", text='{"value": 7}')]
        )

        with (
            patch("compliance.llm.anthropic_api.anthropic.Anthropic"),
            patch(
                "compliance.llm.anthropic_api._call_model",
                return_value=response,
            ) as mock_call_model,
        ):
            result = call_structured_model(
                "system text",
                "user text",
                response_model=ExampleModel,
                ai_model="claude-test",
                prompt_version="v-test",
            )

        assert result == ExampleModel(value=7)
        assert mock_call_model.call_args.kwargs["response_model"] is ExampleModel

    def test_uses_default_ai_model_when_not_provided(self) -> None:
        response = SimpleNamespace(
            content=[TextBlock(type="text", text='{"value": 7}')]
        )

        with (
            patch("compliance.llm.anthropic_api.anthropic.Anthropic"),
            patch(
                "compliance.llm.anthropic_api._call_model", return_value=response
            ) as mock_call_model,
        ):
            call_structured_model(
                "system text",
                "user text",
                response_model=ExampleModel,
            )

        assert mock_call_model.call_args.kwargs["ai_model"] == (
            anthropic_api._DEFAULT_AI_MODEL
        )

    def test_raises_type_error_when_response_model_is_not_pydantic_model(self) -> None:
        with pytest.raises(TypeError, match="Pydantic BaseModel"):
            call_structured_model(
                "system text",
                "user text",
                response_model=dict,
            )

    def test_raises_type_error_when_response_model_is_not_base_model_instance(
        self,
    ) -> None:
        with pytest.raises(TypeError, match="Pydantic BaseModel"):
            call_structured_model(
                "system text",
                "user text",
                response_model=ExampleModel(value=7),
            )

    def test_loads_dotenv_without_overriding_existing_environment(self) -> None:
        response = SimpleNamespace(
            content=[TextBlock(type="text", text='{"value": 7}')]
        )

        with (
            patch("compliance.llm.anthropic_api.load_dotenv") as mock_load_dotenv,
            patch("compliance.llm.anthropic_api.anthropic.Anthropic"),
            patch(
                "compliance.llm.anthropic_api._call_model",
                return_value=response,
            ),
        ):
            call_structured_model(
                "system text",
                "user text",
                response_model=ExampleModel,
            )

        mock_load_dotenv.assert_called_once()
        assert mock_load_dotenv.call_args.kwargs["override"] is False


class TestCallModel:
    def test_calls_messages_create_with_expected_payload(self) -> None:
        client = MagicMock()
        schema = {"type": "object"}
        client.messages.create.return_value = _model_response()

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value=schema,
        ):
            _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        client.messages.create.assert_called_once_with(
            model="claude-test",
            max_tokens=anthropic_api._MAX_TOKENS,
            system="system text",
            messages=[{"role": "user", "content": "user text"}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )

    def test_returns_messages_create_response(self) -> None:
        client = MagicMock()
        response = _model_response()
        client.messages.create.return_value = response

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value={"type": "object"},
        ):
            result = _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        assert result == response

    def test_raises_type_error_when_response_model_is_not_pydantic_model(self) -> None:
        with pytest.raises(TypeError, match="Pydantic BaseModel"):
            _call_model(
                client=MagicMock(),
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=dict,
            )

    def test_retry_decorator_returns_response_after_retryable_error(self) -> None:
        client = MagicMock()
        response = _model_response()
        client.messages.create.side_effect = [_api_status_error(503), response]

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value={"type": "object"},
        ):
            result = _call_model.retry_with(wait=wait_none())(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        assert result == response
        assert client.messages.create.call_count == 2

    def test_continues_when_end_turn_response_has_no_content(self) -> None:
        client = MagicMock()
        first_response_tokens = 25
        response = _model_response()
        client.messages.create.side_effect = [
            _model_response(content=[], total_tokens=first_response_tokens),
            response,
        ]

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value={"type": "object"},
        ):
            result = _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        assert result == response
        assert client.messages.create.call_count == 2
        assert client.messages.create.call_args_list[1].kwargs["max_tokens"] == (
            anthropic_api._MAX_TOKENS - first_response_tokens
        )
        assert client.messages.create.call_args_list[1].kwargs["messages"] == [
            {"role": "user", "content": "user text"},
            {"role": "user", "content": "Please continue"},
        ]

    @pytest.mark.parametrize(
        ("stop_reason", "match"),
        [
            ("max_tokens", "Reached max tokens"),
            ("tool_use", "Tool use not yet implemented"),
            ("refusal", "safety concerns"),
            ("model_context_window_exceeded", "context window limit"),
        ],
    )
    def test_raises_value_error_for_terminal_stop_reasons(
        self, stop_reason, match
    ) -> None:
        client = MagicMock()
        client.messages.create.return_value = _model_response(stop_reason=stop_reason)

        with (
            patch(
                "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
                return_value={"type": "object"},
            ),
            pytest.raises(ValueError, match=match),
        ):
            _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

    def test_continues_after_pause_turn_response(self) -> None:
        client = MagicMock()
        pause_response_tokens = 25
        pause_response = _model_response(
            stop_reason="pause_turn",
            total_tokens=pause_response_tokens,
        )
        final_response = _model_response()
        client.messages.create.side_effect = [pause_response, final_response]

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value={"type": "object"},
        ):
            result = _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        assert result == final_response
        assert client.messages.create.call_count == 2
        assert client.messages.create.call_args_list[1].kwargs["max_tokens"] == (
            anthropic_api._MAX_TOKENS - pause_response_tokens
        )
        assert client.messages.create.call_args_list[1].kwargs["messages"] == [
            {"role": "user", "content": "user text"},
            {"role": "user", "content": "user text"},
            {"role": "assistant", "content": pause_response.content},
        ]

    def test_raises_value_error_when_continuation_exceeds_token_limit(self) -> None:
        client = MagicMock()
        client.messages.create.return_value = _model_response(
            content=[],
            total_tokens=anthropic_api._MAX_TOKENS + 1,
        )

        with (
            patch(
                "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
                return_value={"type": "object"},
            ),
            pytest.raises(ValueError, match="exceeded the max_tokens limit"),
        ):
            _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

    @pytest.mark.parametrize(
        ("exception_factory", "expected_attempts"),
        [
            (lambda: _api_status_error(400), 1),
            (lambda: _api_status_error(408), 6),
            (lambda: _api_status_error(418), 2),
            (lambda: _api_status_error(503), 6),
            (_api_connection_error, 6),
            (_api_timeout_error, 6),
        ],
    )
    def test_retry_decorator_stops_at_exception_specific_attempt_limit(
        self, exception_factory, expected_attempts
    ) -> None:
        client = MagicMock()
        errors = [exception_factory() for _ in range(expected_attempts)]
        client.messages.create.side_effect = errors

        with (
            patch(
                "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
                return_value={"type": "object"},
            ),
            pytest.raises(type(errors[-1])),
        ):
            _call_model.retry_with(wait=wait_none())(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        assert client.messages.create.call_count == expected_attempts

    def test_retry_decorator_does_not_retry_unhandled_exceptions(self) -> None:
        client = MagicMock()
        client.messages.create.side_effect = RuntimeError("boom")

        with (
            patch(
                "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
                return_value={"type": "object"},
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            _call_model.retry_with(wait=wait_none())(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
                response_model=ExampleModel,
            )

        client.messages.create.assert_called_once()


class TestDynamicStopByError:
    def test_stops_after_two_attempts_when_outcome_is_missing(self) -> None:
        assert dynamic_stop_by_error(_retry_state(1, None)) is False
        assert dynamic_stop_by_error(_retry_state(2, None)) is True

    @pytest.mark.parametrize("status_code", [408, 429, 500, 504, 529])
    def test_transient_api_status_errors_stop_after_six_attempts(
        self, status_code
    ) -> None:
        error = _api_status_error(status_code)

        assert dynamic_stop_by_error(_retry_state(5, error)) is False
        assert dynamic_stop_by_error(_retry_state(6, error)) is True

    @pytest.mark.parametrize("status_code", [400, 401, 402, 403, 404, 413, 422])
    def test_non_retryable_api_status_errors_stop_after_one_attempt(
        self, status_code
    ) -> None:
        error = _api_status_error(status_code)

        assert dynamic_stop_by_error(_retry_state(1, error)) is True

    @pytest.mark.parametrize("status_code", [409, 418, 499])
    def test_other_api_status_errors_stop_after_two_attempts(self, status_code) -> None:
        error = _api_status_error(status_code)

        assert dynamic_stop_by_error(_retry_state(1, error)) is False
        assert dynamic_stop_by_error(_retry_state(2, error)) is True

    @pytest.mark.parametrize(
        "exception_factory",
        [
            _api_connection_error,
            _api_timeout_error,
        ],
    )
    def test_connection_errors_stop_after_six_attempts(self, exception_factory) -> None:
        error = exception_factory()

        assert dynamic_stop_by_error(_retry_state(5, error)) is False
        assert dynamic_stop_by_error(_retry_state(6, error)) is True

    def test_other_retryable_errors_stop_after_one_attempt(self) -> None:
        error = RuntimeError("boom")

        assert dynamic_stop_by_error(_retry_state(1, error)) is True


class TestConvertBaseModelToJsonSchema:
    def test_transforms_model_json_schema(self) -> None:
        with patch(
            "compliance.llm.anthropic_api.transform_schema",
            return_value={"transformed": True},
        ) as mock_transform:
            result = _convert_base_model_to_json_schema(ExampleModel)

        mock_transform.assert_called_once_with(ExampleModel.model_json_schema())
        assert result == {"transformed": True}


class TestConvertResponseToModelType:
    def test_parses_plain_json_response(self, response_factory) -> None:
        response = response_factory('{"value": 7}')

        result = _convert_response_to_model_type(response, ExampleModel)

        assert result == ExampleModel(value=7)

    def test_removes_json_code_fence_before_parsing(self, response_factory) -> None:
        response = response_factory('```json\n{"value": 7}\n```')

        result = _convert_response_to_model_type(response, ExampleModel)

        assert result == ExampleModel(value=7)

    def test_raises_json_decode_error_for_invalid_json(self, response_factory) -> None:
        response = response_factory("not valid json")

        with pytest.raises(json.JSONDecodeError):
            _convert_response_to_model_type(response, ExampleModel)

    def test_raises_validation_error_for_schema_invalid_json(
        self, response_factory
    ) -> None:
        response = response_factory(json.dumps({"other": 71}))

        with pytest.raises(ValidationError):
            _convert_response_to_model_type(response, ExampleModel)


class TestExtractTextFromResponse:
    def test_returns_text_when_first_content_item_is_text_block(
        self, response_factory
    ) -> None:
        response = response_factory("hello world")

        assert _extract_text_from_response(response) == "hello world"

    def test_raises_when_response_has_no_content(self) -> None:
        response = SimpleNamespace(content=[])

        with pytest.raises(ValueError, match="does not contain text"):
            _extract_text_from_response(response)

    def test_raises_when_first_content_item_is_not_text_block(self) -> None:
        response = SimpleNamespace(content=[{"type": "text", "text": "hello"}])

        with pytest.raises(ValueError, match="does not contain text"):
            _extract_text_from_response(response)


class TestCreateErrorMessage:
    def test_builds_error_message_with_context(self) -> None:
        result = _create_error_message(
            case_info="case-1",
            ai_model="claude-test",
            system_context="system text",
            user_message="user text",
            response="response text",
        )

        assert "case-1" in result
        assert "claude-test" in result
        assert "system text" in result
        assert "user text" in result
        assert "response text" in result
        assert str(anthropic_api._MAX_TOKENS) in result


class TestParseMessageToString:
    def test_returns_text_when_response_contains_text_block(
        self, response_factory
    ) -> None:
        response = response_factory("hello world")

        assert _parse_message_to_string(response) == "hello world"

    def test_returns_empty_string_when_response_has_no_content(self) -> None:
        response = SimpleNamespace(content=[])

        assert _parse_message_to_string(response) == ""

    def test_returns_empty_string_when_first_content_item_is_not_text_block(
        self,
    ) -> None:
        response = SimpleNamespace(content=[{"type": "text", "text": "hello"}])

        assert _parse_message_to_string(response) == ""


class TestLogValidationErrorMessages:
    def test_logs_each_validation_error(self) -> None:
        error = ValidationError.from_exception_data(
            "ExampleModel",
            [
                {"type": "missing", "loc": ("value",), "input": {}},
                {"type": "int_parsing", "loc": ("value",), "input": "abc"},
            ],
        )

        with patch("compliance.llm.anthropic_api.logger.debug") as mock_debug:
            _log_validation_error_messages(error)

        assert mock_debug.call_count == 2

    def test_logs_error_type_location_and_input(self) -> None:
        error = ValidationError.from_exception_data(
            "ExampleModel",
            [{"type": "missing", "loc": ("value",), "input": {}}],
        )

        with patch("compliance.llm.anthropic_api.logger.debug") as mock_debug:
            _log_validation_error_messages(error)

        logged_message = mock_debug.call_args[0][0]
        assert "Error type: missing" in logged_message
        assert "Location:   ('value',)" in logged_message
        assert "Faulty data: {}" in logged_message
