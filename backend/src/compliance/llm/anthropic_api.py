import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import anthropic
from anthropic.types import Message, TextBlock
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

MAX_TOKENS = 2500
_DEFAULT_PROMPT_VERSION = "v0.1"
_DEFAULT_AI_MODEL = "claude-haiku-4-5-20251001"

logger = logging.getLogger(__name__)
_ROOT_DIR = Path(__file__).resolve().parents[4]
_DOTENV_PATH = _ROOT_DIR / "backend" / ".env"
_SUPPORTED_STRING_FORMATS = {
    "date-time",
    "time",
    "date",
    "duration",
    "email",
    "hostname",
    "uri",
    "ipv4",
    "ipv6",
    "uuid",
}


def call_structured_model[
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
    try:
        is_retry = False
        response = _call_model(
            client=client,
            ai_model=ai_model,
            system_context=system_context,
            user_message=user_message,
            response_model=response_model,
        )
        structured_output = _convert_response_to_model_type(response, response_model)

    except (json.JSONDecodeError, ValidationError) as e:
        is_retry = True
        logger.warning(
            _create_error_message(
                case_info=case_info,
                ai_model=ai_model,
                system_context=system_context,
                user_message=user_message,
                response=_parse_message_to_string(response),
            )
        )

        if isinstance(e, ValidationError):
            _log_validation_error_messages(e)

        added_context = (
            "Your previous response did not match the required schema. I got "
            f"ValidationError: {e}. Return only valid structured output matching "
            f"{response_model}. Original message:"
        )
        try:
            response = _call_model(
                client=client,
                ai_model=ai_model,
                system_context=system_context,
                user_message=added_context + user_message,
                response_model=response_model,
            )
            structured_output = _convert_response_to_model_type(
                response, response_model
            )
        except ValidationError as err:
            logger.error(
                _create_error_message(
                    case_info=case_info,
                    ai_model=ai_model,
                    system_context=system_context,
                    user_message=user_message,
                    response=_parse_message_to_string(response),
                )
            )
            _log_validation_error_messages(err)
            raise

    logger.info(
        f"Timestamp: {datetime.now()}, "
        f"model: {ai_model}, prompt version: {prompt_version}, "
        f"retry used: {is_retry}"
    )
    logger.debug(f"response: {_parse_message_to_string(response)}")

    return structured_output


def transform_schema(json_schema: dict[str, Any]) -> dict[str, Any]:
    """Return an Anthropic-compatible subset of a JSON schema."""
    strict_schema: dict[str, Any] = {}
    json_schema = {**json_schema}

    ref = json_schema.pop("$ref", None)
    if ref is not None:
        strict_schema["$ref"] = ref
        return strict_schema

    defs = json_schema.pop("$defs", None)
    if isinstance(defs, dict):
        strict_schema["$defs"] = {
            name: transform_schema(cast("dict[str, Any]", schema))
            for name, schema in defs.items()
        }

    type_ = json_schema.pop("type", None)
    any_of = json_schema.pop("anyOf", None)
    one_of = json_schema.pop("oneOf", None)
    all_of = json_schema.pop("allOf", None)

    if isinstance(any_of, list):
        strict_schema["anyOf"] = [
            transform_schema(cast("dict[str, Any]", variant)) for variant in any_of
        ]
    elif isinstance(one_of, list):
        strict_schema["anyOf"] = [
            transform_schema(cast("dict[str, Any]", variant)) for variant in one_of
        ]
    elif isinstance(all_of, list):
        strict_schema["allOf"] = [
            transform_schema(cast("dict[str, Any]", variant)) for variant in all_of
        ]
    elif type_ is None:
        raise ValueError("Schema must have a type, anyOf, oneOf, or allOf field.")
    else:
        strict_schema["type"] = type_

    enum = json_schema.pop("enum", None)
    if isinstance(enum, list):
        strict_schema["enum"] = enum

    description = json_schema.pop("description", None)
    if description is not None:
        strict_schema["description"] = description

    title = json_schema.pop("title", None)
    if title is not None:
        strict_schema["title"] = title

    if type_ == "object":
        properties = json_schema.pop("properties", {})
        strict_schema["properties"] = {
            key: transform_schema(cast("dict[str, Any]", prop_schema))
            for key, prop_schema in properties.items()
        }
        json_schema.pop("additionalProperties", None)
        strict_schema["additionalProperties"] = False

        required = json_schema.pop("required", None)
        if required is not None:
            strict_schema["required"] = required

    elif type_ == "string":
        schema_format = json_schema.pop("format", None)
        if schema_format in _SUPPORTED_STRING_FORMATS:
            strict_schema["format"] = schema_format
        elif schema_format is not None:
            json_schema["format"] = schema_format

    elif type_ == "array":
        items = json_schema.pop("items", None)
        if items is not None:
            strict_schema["items"] = transform_schema(cast("dict[str, Any]", items))

        min_items = json_schema.pop("minItems", None)
        if min_items in (0, 1):
            strict_schema["minItems"] = min_items
        elif min_items is not None:
            json_schema["minItems"] = min_items

    if json_schema:
        description = strict_schema.get("description")
        prefix = f"{description}\n\n" if description is not None else ""
        strict_schema["description"] = (
            prefix
            + "{"
            + ", ".join(f"{key}: {value}" for key, value in json_schema.items())
            + "}"
        )

    return strict_schema


def _call_model(
    *,
    client: anthropic.Anthropic,
    ai_model: str,
    system_context: str,
    user_message: str,
    response_model: type[BaseModel],
) -> Message:
    """Send a structured-output prompt to Anthropic and return the raw response."""
    if not isinstance(response_model, type) or not issubclass(
        response_model, BaseModel
    ):
        raise TypeError(f"{response_model} is not a Pydantic BaseModel.")

    schema = _convert_base_model_to_json_schema(response_model)
    return client.messages.create(
        model=ai_model,
        max_tokens=MAX_TOKENS,
        system=system_context,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
        output_config={
            "format": {"type": "json_schema", "schema": schema},
        },
    )


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
        f" max_tokens={MAX_TOKENS}, system={system_context},"
        f" \nand user_message={user_message}\nresponse: {response}"
    )


def _parse_message_to_string(response: Message) -> str:
    """Return the first response text block as a string, or an empty string."""
    return (
        response.content[0].text
        if (response.content and isinstance(response.content[0], TextBlock))
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
