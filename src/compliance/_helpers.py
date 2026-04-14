from compliance.llm.schemas import EvidenceRef, SiteAnalysis
from compliance.schemas import Site


def validate_llm_references(site_analysis: SiteAnalysis, site_history: Site) -> None:
    """Validates all evidence references within a SiteAnalysis against site history.

    Iterates through specific analysis categories (recurring issues, missing
    info, human review, and suggestions) and ensures every attached
    EvidenceRef points to valid historical data.

    Args:
        site_analysis: The structured output from the LLM containing
            claims and evidence references.
        site_history: The ground-truth site data used for verification.

    Raises:
        ValueError: If any evidence reference contains an ID or metadata
            that does not exist in the site history.
    """
    for site_attr in [
        "recurring_issues",
        "missing_information",
        "needs_human_review",
        "suggestions",
    ]:
        attr_list = getattr(site_analysis, site_attr, list())
        if not attr_list:
            continue
        for item in attr_list:
            evidence_refs = item.evidence
            for evidence in evidence_refs:
                _validate_evidence_ref(evidence, site_history)


def _validate_evidence_ref(evidence: EvidenceRef, site_history: Site) -> None:
    """Verifies a single evidence reference against historical records.

    Performs a cascading check to ensure the certification ID exists,
    the inspection date matches, and any cited finding ID or rule index
    is consistent with the recorded findings for that certification.

    Args:
        evidence: The specific evidence reference to validate.
        site_history: The ground-truth site data containing certifications
            and findings.

    Returns:
        None

    Raises:
        ValueError: If the certification ID is missing, the date is
            incorrect, the finding ID is not found within the certification,
            or the rule index does not match the cited finding.
    """
    cert = next(
        (c for c in site_history.certifications if c.cert_id == evidence.cert_id), None
    )
    if not cert:
        raise ValueError(f"Certification {evidence.cert_id} is not in site history.")

    if evidence.reg_title and cert.reg_title != evidence.reg_title:
        raise ValueError(
            f"Wrong regulation title for certification {evidence.cert_id} "
            f": {evidence.reg_title}."
        )

    if evidence.inspection_date and cert.inspection_date != evidence.inspection_date:
        raise ValueError(
            f"Wrong inspection date for certification {evidence.cert_id} "
            f": {evidence.inspection_date}."
        )

    if evidence.finding_id is not None:
        finding = next(
            (f for f in cert.findings if f.finding_id == evidence.finding_id), None
        )
        if not finding:
            raise ValueError(
                f"Finding {evidence.finding_id} is not in"
                f" certification {evidence.cert_id}."
            )

        if evidence.rule_index and evidence.rule_index != finding.rule_index:
            raise ValueError(
                f"Wrong rule index for finding {evidence.finding_id} "
                f"in certification {evidence.cert_id}."
            )

    if evidence.finding_id is None and evidence.rule_index is not None:
        raise ValueError(
            f"Rule index should not exist if no finding id is available. "
            f"Certification {evidence.cert_id}"
        )

    return
