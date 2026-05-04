from datetime import datetime

from compliance.llm.schemas import EvidenceRef, SiteAnalysis


def build_site_analysis_markdown(site_analysis: SiteAnalysis) -> str:
    """Render a SiteAnalysis object as a Markdown summary document."""

    output_text = (
        f"# Site Analysis\n## Metadata\n**Site ID:** {site_analysis.site_id}"
        f"\n**Generated at:** {datetime.now()}\n**Note:** Everything in this"
        f" report is AI-generated and is meant for human-review-only.  "
        f"These are not official compliance decisions.\n## Executive summary"
    )
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
