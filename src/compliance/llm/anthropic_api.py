import json
import logging
import pprint
from datetime import datetime

import anthropic
from anthropic.types import Message
from dotenv import load_dotenv
from pydantic import ValidationError

from compliance.app import get_site_history
from compliance.schemas import Site, SiteAnalysis

MAX_TOKENS = 2500
_DEFAULT_PROMPT_VERSION = "v1.1"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()


def summarize_previous_visits(
    site_history: Site, *, ai_model: str, case_info: str = ""
) -> tuple[bool, str, SiteAnalysis]:
    Site.model_validate(site_history)

    system_context = """You are assisting with inspection-history analysis.
    
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
    - list caveats about interpreting the history
    - make a suggestion of things an inspector should pay attention to during a visit based 
    on previous visits and regulation and rule descriptions.
    
    Field guidance:
    - summary: short factual overview
    - recurring_issues: repeated problems supported by the history.  Only repeated issues 
    supported by more than one certification or repeated rule/finding pattern.
    - missing_information: facts that are absent or unclear
    - needs_human_review: places where a person should verify or interpret.  Be sure to 
    cite the regulation title, rule index and rule title if available.  Should name ambiguity 
    or interpretation boundary, not just "review this".
    - inspection_caveats: limits of the available history/data
    - suggestions: suggestions for preparing for the visit and for 
    during the visit.  Must be framed as preparation suggestions, not conclusions.  Must 
    be tied to the provided findings/regulations/rules.
    
    General:
    - When describing inspections and certifications, cite the regulation title if available.
    - When describing findings, cite the regulation title, rule index and rule title if available.
    
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
            is_retry=is_retry,
        )
        SiteAnalysis.model_validate(response)
    except ValidationError as e:
        is_retry = True
        logger.warning(
            _create_error_message(
                case_info=case_info,
                ai_model=ai_model,
                system_context=system_context,
                user_message=user_message,
                response=_parse_message(response)
            )
        )
        _log_validation_error_messages(e)

        # retry with added context
        added_context = f"Your previous response did not match the required schema. I got ValidationError: {e}. Return only valid structured output matching SiteAnalysis. Original message:"
        try:
            response = _call_model(
                client=client,
                ai_model=ai_model,
                system_context=system_context,
                user_message=added_context + user_message,
                is_retry=is_retry,
            )
            SiteAnalysis.model_validate(response)
        except ValidationError as err:

            logger.error(
                _create_error_message(
                    case_info=case_info,
                    ai_model=ai_model,
                    system_context=system_context,
                    user_message=user_message,
                    response=_parse_message(response)
                )
            )
            _log_validation_error_messages(err)
            raise

    logger.info(
        f"Timestamp: {datetime.now()}, site id: {site_history.site_id}, "
        f"model: {ai_model}, prompt version: {_DEFAULT_PROMPT_VERSION}, "
        f"retry used: {is_retry}"
    )
    logger.info(f"response: {response}")
    pprint.pp(_parse_message(response))
    pprint.pp(response)

    return is_retry, _DEFAULT_PROMPT_VERSION, SiteAnalysis.model_validate(response)


def _call_model(
    *,
    client: anthropic.Anthropic,
    ai_model: str,
    system_context: str,
    user_message: str,
    is_retry: bool,
) -> Message:
    """Send a user message to the model and parse the response into a site analysis.

    Args:
        client: Configured Anthropic client used to send the request.
        ai_model: The AI model and version
        system_context: System prompt that defines the model's behavior.
        user_message: End-user message to analyze.
        is_retry: Are we calling the model after the first call failed?

    Returns:
        anthropic.Anthropic: Model response.

    Raises:
        anthropic.APIError: If the API request fails.
        anthropic.APIConnectionError: If the client cannot reach the API.
        anthropic.RateLimitError: If the request is rate-limited.
        Exception: If the response cannot be parsed into ``SiteAnalysis``.
    """
    if is_retry:
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
        )
    else:
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
        )


def _parse_message(response: Message) -> str:
    if response.content and isinstance(response.content[0], dict) and "text" in response.content[0]:
            return response.content[0].text

    return ""

def _create_error_message(
    *, case_info: str, ai_model: str, system_context: str, user_message: str, response: str
) -> str:
    return f"Model failed for case: {case_info}, model={ai_model} max_tokens={MAX_TOKENS}, system={system_context}, \nand user_message={user_message}\nresponse: {response}"


def _log_validation_error_messages(err: ValidationError) -> None:
    for error in err.errors():
        logger.debug(
            f"Error type: {error['type']}\nLocation:   {error['loc']}\nFaulty data: {error['input']}"
        )


if __name__ == "__main__":
    site_history = get_site_history(71)
    if site_history is None:
        raise ValueError("site_history is None")
    summarize_previous_visits(site_history, ai_model="claude-haiku-4-5-20251001")  #
