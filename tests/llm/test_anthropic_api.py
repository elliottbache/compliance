import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock
from pydantic import BaseModel, ValidationError

import compliance.llm.anthropic_api as anthropic_api
from compliance.llm.anthropic_api import (
    _call_model,
    _convert_base_model_to_json_schema,
    _convert_response_to_model_type,
    _create_error_message,
    _extract_text_from_response,
    _log_validation_error_messages,
    _parse_message_to_string,
    call_structured_model,
)


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


class TestCallModel:
    def test_calls_messages_create_with_expected_payload(self) -> None:
        client = MagicMock()
        schema = {"type": "object"}

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
            max_tokens=anthropic_api.MAX_TOKENS,
            system="system text",
            messages=[{"role": "user", "content": "user text"}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )

    def test_returns_messages_create_response(self) -> None:
        client = MagicMock()
        response = MagicMock()
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
        assert str(anthropic_api.MAX_TOKENS) in result


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
