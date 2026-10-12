import json

import pytest
from compliance.llm._helpers import raise_or_create_format_repair_prompt
from pydantic import BaseModel, ValidationError


class _ExampleResponse(BaseModel):
    value: int


def _validation_error() -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        _ExampleResponse.model_validate({"value": "not-an-integer"})
    return exc_info.value


class TestRaiseOrCreateFormatRepairPrompt:
    def test_returns_repair_prompt_after_first_format_error(self) -> None:
        error = _validation_error()

        result = raise_or_create_format_repair_prompt(
            error,
            system_context="system",
            user_message="user",
            added_context="",
            response_model=_ExampleResponse,
            ai_model="test-model",
            case_info="test-case",
            response_text='{"value": "invalid"}',
            max_tokens=100,
        )

        assert "did not match the required schema" in result
        assert "ValidationError" in result
        assert "_ExampleResponse" in result

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(_validation_error(), id="validation-error"),
            pytest.param(json.JSONDecodeError("invalid JSON", "{", 1), id="json-error"),
        ],
    )
    def test_reraises_second_format_error(self, error) -> None:
        with pytest.raises(type(error)) as exc_info:
            raise_or_create_format_repair_prompt(
                error,
                system_context="system",
                user_message="user",
                added_context="previous repair request",
                response_model=_ExampleResponse,
                ai_model="test-model",
                case_info="test-case",
                response_text="invalid",
                max_tokens=100,
            )

        assert exc_info.value is error
