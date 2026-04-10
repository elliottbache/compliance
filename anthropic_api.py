import anthropic
import json
import logging
import pprint

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from app import get_site_history
from schemas import Site, SiteAnalysis

AI_MODEL = "claude-haiku-4-5-20251001"  # other options: claude-opus-4-6
MAX_TOKENS = 1000


logger = logging.getLogger(__name__)

load_dotenv()


def summarize_previous_visits(site_history: Site | None) -> SiteAnalysis | None:
    if site_history is None:
        logger.warning("No site history found.")
        return None

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
    - recurring_issues: repeated problems supported by the history
    - missing_information: facts that are absent or unclear
    - needs_human_review: places where a person should verify or interpret
    - inspection_caveats: limits of the available history/data
    - suggestions: suggestions for preparing for the visit and for 
    during the visit
    
    Site history:
    """
    user_message += json.dumps(site_history.model_dump(mode="json"), separators=(',', ':'))
    """
    user_message = "What should I search for to find the latest developments in renewable energy?"
    system_context = "Give me a short answer."
    """

    logger.debug(f"system_context: {system_context}")
    logger.debug(f"user_message: {user_message}")

    client = anthropic.Anthropic()
    try:
        response = client.messages.parse(
            model=AI_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_context,
            messages = [
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            output_format=SiteAnalysis,
        )
    except ValidationError as e:
        logger.warning(_create_error_message(system_context, user_message))
        _log_validation_error_messages(e)

        added_context = f"Your previous response did not match the required schema. I got ValidationError: {e}. Return only valid structured output matching SiteAnalysis. Original message:"
        try:
            response = client.messages.parse(
                model=AI_MODEL,
                max_tokens=MAX_TOKENS,
                system=system_context,
                messages=[
                    {
                        "role": "user",
                        "content": added_context + user_message,
                    }
                ],
                output_format=SiteAnalysis,
            )
        except ValidationError as err:
            logger.error(_create_error_message(system_context, user_message))
            _log_validation_error_messages(err)
            raise

    logger.debug(f"response: {response}")
    pprint.pp(response.parsed_output)
    pprint.pp(response)

    return response.parsed_output


def _create_error_message(system_context: str, user_message:str) -> str:
    return f"Model failed for model={AI_MODEL} max_tokens={MAX_TOKENS}, system={system_context}, and user_message={user_message}"


def _log_validation_error_messages(err: ValidationError) -> None:
    for error in err.errors():
        logger.debug(f"Error Type: {error['type']}\nLocation:   {error['loc']}\nFaulty Data: {error['input']}")


if __name__ == "__main__":
    site_history = get_site_history(71)
    summarize_previous_visits(site_history)