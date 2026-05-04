import json
import logging

from compliance.llm.anthropic_api import call_structured_model
from compliance.llm.schemas import EvidenceRef, SiteAnalysis
from compliance.schemas import SiteHistory

logger = logging.getLogger(__name__)


def summarize_previous_visits(
    site_history: SiteHistory,
    *,
    ai_model: str = "claude-haiku-4-5-20251001",
    prompt_version: str = "v1.2",
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


def render_site_analysis_markdown(site_analysis: SiteAnalysis) -> str:
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
    
    Site history:
    """
    user_message += json.dumps(
        site_history.model_dump(mode="json"), separators=(",", ":")
    )

    return user_message


def _render_site_analysis_attribute(site_analysis: SiteAnalysis, attr_name: str) -> str:
    """Render one SiteAnalysis list attribute and its evidence as Markdown."""

    attr = getattr(site_analysis, attr_name, None)
    if not attr or not isinstance(attr, list):
        return "\nNone."

    output_text = ""
    for attr_element in attr:
        output_text += f"\n### {attr_element.item}"
        # Render fields such as confidence_note, why_missing_matters, or basis.
        for sub_attr, value in vars(attr_element).items():
            if sub_attr in ["item", "evidence"]:
                continue
            output_text += f"\n#### {_beautify_attr_name(sub_attr)}\n{value}"
        for evidence in attr_element.evidence:
            output_text += _format_evidence_item_to_markdown(evidence)

    return output_text


def _beautify_attr_name(attr_name: str) -> str:
    """Convert an internal attribute name into a display-friendly section label."""

    return attr_name.capitalize().replace("_", " ")


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
    from compliance.logging_utils import configure_logging

    configure_logging(level="DEBUG")

    from compliance.services.records import get_site_history_legacy

    site_history = get_site_history_legacy(71)
    if site_history is None:
        raise ValueError("site_history is None")

    print(summarize_previous_visits(site_history))
