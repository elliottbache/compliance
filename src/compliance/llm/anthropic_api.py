import json
import logging
from datetime import datetime
from typing import Any

import anthropic
from anthropic import transform_schema
from anthropic.types import Message, TextBlock
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from compliance.db.query_history import get_site_history
from compliance.llm.schemas import EvidenceRef, SiteAnalysis
from compliance.logging_utils import configure_logging
from compliance.schemas import Site

MAX_TOKENS = 2500
_DEFAULT_PROMPT_VERSION = "v1.2"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()


def summarize_previous_visits(
    site_history: Site, *, ai_model: str, case_info: str = ""
) -> tuple[bool, str, SiteAnalysis]:
    """Analyzes site history using an AI model to generate a structured summary.

    This function prepares a prompt containing the site history and specific
    analytical guidelines, calls an Anthropic AI model, and parses the result into
    a structured SiteAnalysis object. It includes a single retry mechanism if the
    initial model output fails JSON validation or schema compliance.

    Args:
        site_history: A Site object containing the historical data to be analyzed.
        ai_model: The name/ID of the Anthropic model to use for the analysis.
        case_info: Optional metadata or identifier for the current case,
            used primarily for error logging. Defaults to an empty string.

    Returns:
        A tuple containing:
            - is_retry (bool): True if the analysis required a second attempt
              due to a validation error.
            - prompt_version (str): The version string of the prompt used.
            - site_analysis (SiteAnalysis): The validated structured output
              containing the summary, recurring issues, and suggestions.

    Raises:
        ValidationError: If the model output cannot be parsed into a
            SiteAnalysis object even after a retry.
        json.JSONDecodeError: If the model returns invalid JSON that cannot
            be recovered.
    """
    Site.model_validate(site_history)

    system_context = """You are assisting with inspection-history analysis for an 
    inspector.
    
    Use only the facts provided.
    Do not invent missing facts.
    If something is unclear or absent, put it in missing_information.
    Do not make compliance decisions or legal judgments.
    You can make suggestions, but make sure it is stated that they are only suggestions.
    Return output that matches the requested schema exactly."""

    user_message = """Analyze the following site history.
    
    Goal:
    - write a concise factual summary
    - identify recurring issues only when supported by repeated findings/history
    - list missing information
    - list reasons a human should review
    - make a suggestion of things an inspector should pay attention to during a visit based 
    on previous visits and regulation and rule descriptions.
    
    Field guidance:
    - executive_summary: short factual overview
    - recurring_issues: repeated problems supported by the history.  Only repeated issues 
    supported by more than one certification or repeated rule/finding pattern.  Requires
    at least 2 evidence references.
    - missing_information: facts that are absent or unclear.  If a data field has an 
    empty list or dict, None or null, verify if this makes sense.  If it doesn't, 
    missing_information should document it.  Do not place missing information in the 
    executive_summary.  Do not add things that do not directly affect the validity or confidence
    in the certification.  Missing findings should go here.
    - needs_human_review: places where a person should verify or interpret.  Be sure to 
    cite the regulation title, rule index and rule title if available.  Should name ambiguity 
    or interpretation boundary, not just "review this".  Do not question the validity of
    the inspector's conclusions.
    - suggestions: suggestions for preparing for the visit and for 
    during the visit.  Must be framed as preparation suggestions, not conclusions.  Must 
    be tied to the provided findings/regulations/rules.
    - For all of these except executive_summary, attach a reference to the piece(s) of evidence.
    Attach a reference to the certification and possibly finding, rule, or regulation if they apply.
    
    General:
    - Maintenance records are not available nor will they ever be.
    - Corrective actions are also not available.
    - Resolution dates can acceptably be null if the status is "In progress" or "Fail".
    They should not be null for "Pass".
    - Pass grades do not require findings.  Fail grades do.
    
    Site history:
    """
    user_message += json.dumps(
        site_history.model_dump(mode="json"), separators=(",", ":")
    )
    """
    user_message = "What should I search for to find the latest developments in renewable energy?"
    system_context = "Give me a short answer."
    """

    logger.debug(f"system_context: {system_context}")
    logger.debug(f"user_message: {user_message}")

    client = anthropic.Anthropic()
    try:
        is_retry = False
        response = _call_model(
            client=client,
            ai_model=ai_model,
            system_context=system_context,
            user_message=user_message,
        )
        site_analysis = _convert_response_to_site_analysis(response)

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
        # retry with added context
        added_context = f"Your previous response did not match the required schema. I got ValidationError: {e}. Return only valid structured output matching SiteAnalysis. Original message:"
        try:
            response = _call_model(
                client=client,
                ai_model=ai_model,
                system_context=system_context,
                user_message=added_context + user_message,
            )
            site_analysis = _convert_response_to_site_analysis(response)
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
            if isinstance(e, ValidationError):
                _log_validation_error_messages(err)
            raise

    logger.info(
        f"Timestamp: {datetime.now()}, site id: {site_history.site_id}, "
        f"model: {ai_model}, prompt version: {_DEFAULT_PROMPT_VERSION}, "
        f"retry used: {is_retry}"
    )
    logger.debug(f"response: {_parse_message_to_string(response)}")

    markdown_text = _render_site_analysis_markdown(site_analysis)
    print(markdown_text)

    return is_retry, _DEFAULT_PROMPT_VERSION, site_analysis


def _call_model(
    *,
    client: anthropic.Anthropic,
    ai_model: str,
    system_context: str,
    user_message: str,
) -> Message:
    """Send the prompt to Anthropic and return the raw message response.

    Args:
        client: Configured Anthropic client used to send the request.
        ai_model: The model name to use for the request.
        system_context: System prompt that defines the model's behavior.
        user_message: User prompt containing the site history to analyze.

    Returns:
        The raw Anthropic message response.

    Raises:
        anthropic.APIError: If the API request fails.
        anthropic.APIConnectionError: If the client cannot reach the API.
        anthropic.RateLimitError: If the request is rate-limited.
    """
    schema = _convert_base_model_to_json_schema(SiteAnalysis)
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


def _convert_response_to_site_analysis(response: Message) -> SiteAnalysis:
    """Parse a model response into a validated SiteAnalysis object."""

    raw_text = _extract_text_from_response(response)
    if "```json" in raw_text:
        clean_text = (
            raw_text.strip().removeprefix("```json").removesuffix("```").strip()
        )
    else:
        clean_text = raw_text
    data_dict = json.loads(clean_text)
    return SiteAnalysis.model_validate(data_dict)


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
            f"Error type: {error['type']}\nLocation:   {error['loc']}\nFaulty data: {error['input']}"
        )


def _render_site_analysis_markdown(site_analysis: SiteAnalysis) -> str:
    """Render a SiteAnalysis object as a Markdown summary document."""

    output_text = "# Site Analysis\n## Executive summary"
    exec_text = (
        site_analysis.executive_summary if site_analysis.executive_summary else "None."
    )
    output_text += "\n" + exec_text
    for attr in [
        "recurring_issues",
        "missing_information",
        "needs_human_review",
        "suggestions",
    ]:
        output_text += f"\n## {_beautify_attr_name(attr)}"
        output_text += _render_site_analysis_attribute(site_analysis, attr)

    return output_text


def _beautify_attr_name(attr_name: str) -> str:
    """Convert an internal attribute name into a display-friendly section label."""

    return attr_name.capitalize().replace("_", " ")


def _render_site_analysis_attribute(site_analysis: SiteAnalysis, attr_name: str) -> str:
    """Render one SiteAnalysis list attribute and its evidence as Markdown."""

    attr = getattr(site_analysis, attr_name, None)
    if not attr or not isinstance(attr, list):
        return "\nNone."

    output_text = ""
    for attr_element in attr:
        # .item
        output_text += f"\n### {attr_element.item}"
        # .???
        for sub_attr, value in vars(attr_element).items():
            if sub_attr in ["item", "evidence"]:
                continue
            output_text += f"\n#### {_beautify_attr_name(sub_attr)}\n{value}"
        # .evidence
        for evidence in attr_element.evidence:
            output_text += _format_evidence_item_to_markdown(evidence)

    return output_text


def _format_evidence_item_to_markdown(
    evidence: EvidenceRef, *, header_level: str = "####"
) -> str:
    """Render a single evidence reference as a Markdown bullet section."""

    output_text = f"\n{header_level} Evidence\n- Certification ID: {evidence.cert_id}\n- Regulation title: {evidence.reg_title}"
    if evidence.inspection_date:
        output_text += f"\n- Inspection date: {evidence.inspection_date}"
    if evidence.finding_id:
        output_text += f"\n- Finding ID: {evidence.finding_id}"
    if evidence.rule_index:
        output_text += f"\n- Rule index: {evidence.rule_index}"
    output_text += f"\n- Description: {evidence.support_text}"

    return output_text


if __name__ == "__main__":
    configure_logging(level="DEBUG")

    site_history = get_site_history(71)
    if site_history is None:
        raise ValueError("site_history is None")
    summarize_previous_visits(site_history, ai_model="claude-haiku-4-5-20251001")  #
