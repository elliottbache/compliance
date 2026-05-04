import json
import logging

from compliance.llm.anthropic_api import call_structured_model
from compliance.llm.schemas import SiteAnalysis
from compliance.schemas import SiteHistory

logger = logging.getLogger(__name__)


def summarize_previous_visits(
    site_history: SiteHistory,
    *,
    ai_model: str = "claude-haiku-4-5-20251001",
    prompt_version: str = "v1.3",
    case_info: str = "",
) -> SiteAnalysis:
    """Analyze site history with the site-analysis prompt workflow.

    This service owns the site-specific system prompt and user message, then
    delegates the generic structured-output call to the LLM adapter. The adapter
    returns a validated SiteAnalysis.

    Args:
        site_history: Site history data to summarize and analyze.
        ai_model: Name or ID of the Anthropic model to use for the analysis.
        prompt_version: Version label for the site-analysis prompt.
        case_info: Optional metadata or identifier for the current case,
            used primarily for error logging. Defaults to an empty string.

    Returns:
        The validated structured output containing the summary, recurring
        issues, missing information, review items, and suggestions.

    Raises:
        ValidationError: If the model output cannot be parsed into a
            SiteAnalysis object even after a retry.
        json.JSONDecodeError: If the model returns invalid JSON that cannot
            be recovered.
    """

    system_context = _build_site_analysis_system_prompt()
    user_message = _build_site_analysis_user_message(site_history)

    return call_structured_model(
        system_context,
        user_message,
        response_model=SiteAnalysis,
        ai_model=ai_model,
        prompt_version=prompt_version,
        case_info=case_info,
    )


def _build_site_analysis_system_prompt() -> str:
    """Build the system prompt that defines the site-analysis guardrails."""
    return """You are assisting with inspection-history analysis for an 
    inspector.
    
    Use only the facts provided.
    Do not invent missing facts.
    If something is unclear or absent, put it in missing_information.
    Do not make compliance decisions or legal judgments.
    You can make suggestions, but make sure it is stated that they are only suggestions.
    Return output that matches the requested schema exactly."""


def _build_site_analysis_user_message(site_history: SiteHistory) -> str:
    """Build the user prompt containing instructions and serialized site history."""
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
    - Findings are tied to a rule, which is tied to a regulation, which is tied to a certification
    for a specific site history.  The finding ID cited in evidence must coincide with the cited
    certification.
    
    Site history:
    """
    user_message += json.dumps(
        site_history.model_dump(mode="json"), separators=(",", ":")
    )

    return user_message


if __name__ == "__main__":
    from compliance.logging_utils import configure_logging

    configure_logging(level="DEBUG")

    from compliance.services.records import get_site_history_legacy

    site_history = get_site_history_legacy(71)
    if site_history is None:
        raise ValueError("site_history is None")

    print(summarize_previous_visits(site_history))
