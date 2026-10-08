"""Build deterministic semantic input for RAG clause embeddings."""

import hashlib
import json

from compliance.db.models import RagClause, RagDocument, Site
from compliance.llm.rag.extract_clauses import normalize_text
from compliance.schemas import SiteHistory

EMBEDDING_INPUT_VERSION = 1


def build_site_analysis_query_embedding_input(
    site: Site, site_history: SiteHistory
) -> dict[int, str]:
    """Build labeled embedding text from site history context for RAG retrieval.

    Format:
        123:
            Certifier: Certifier1
            Site: Address1
            Regulation: RegulationTitle1
            Regulation text: RegulationText1
            Rule: RuleIndex1 -- RuleTitle1
            Rule text: RuleText1
            Finding: FindingText1

    """
    site_queries: dict[int, str] = {}
    for certification in site_history.certifications:
        for finding in certification.findings:
            site_query = ""
            site_query += f"Certifier: {certification.certifier_org_name}\n"
            site_query += f"Site: {site.city} {site.postal_code}\n"
            site_query += f"Regulation: {certification.reg_title}\n"
            site_query += f"Regulation text: {certification.reg_description}\n"
            site_query += f"Rule: {finding.rule_index}"
            if finding.rule_title:
                site_query += f" -- {finding.rule_title}\n"
            else:
                site_query += "\n"
            site_query += f"Rule text: {finding.rule_description}\n"
            site_query += f"Finding: {finding.finding}"
            site_queries[finding.finding_id] = site_query

    return site_queries


def build_clause_embedding_input(
    document: RagDocument,
    clause: RagClause,
) -> str:
    """Build labeled embedding text from document and clause context."""
    document_title = _required_text(document.title, "document title")
    source_id = _required_text(document.source_id, "document source ID")
    jurisdiction = _required_text(document.jurisdiction, "document jurisdiction")
    citation_ref = _required_text(clause.citation_ref, "clause citation")
    clause_text = _required_text(clause.text, "clause text")
    path_text = normalize_text(clause.path_text)
    clause_title = normalize_text(clause.title)

    lines = [
        f"Document title: {document_title}",
        f"Source ID: {source_id}",
        f"Jurisdiction: {jurisdiction}",
    ]

    if path_text:
        lines.append(f"Path: {path_text}")

    lines.append(f"Citation: {citation_ref}")

    if clause_title:
        lines.append(f"Clause title: {clause_title}")

    lines.extend(["", "Text:", clause_text])

    return "\n".join(lines)


def build_clause_embedding_input_hash(
    document: RagDocument,
    clause: RagClause,
) -> str:
    """Hash the versioned embedding input used for stale detection."""
    payload = {
        "input": build_clause_embedding_input(document, clause),
        "version": EMBEDDING_INPUT_VERSION,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _required_text(value: object | None, field: str) -> str:
    normalized = normalize_text(value)
    if normalized is None:
        raise ValueError(f"Embedding input requires {field}.")
    return normalized


if __name__ == "__main__":
    from datetime import date

    from compliance.schemas import CertificationHistory, FindingHistory

    sample_site = Site(
        id=101,
        nif="A12345678",
        city="Madrid",
        postal_code=28001,
        street="Mayor",
        street_number=10,
        suite=None,
        address_info=None,
        archived_at=None,
        archive_reason=None,
    )

    sample_site_history = SiteHistory(
        site_id=sample_site.id,
        inspection_count=1,
        latest_inspection_date=date(2026, 9, 15),
        certifications=[
            CertificationHistory(
                cert_id=201,
                result="Fail",
                resolution_date=None,
                reg_title="Workplace Safety Regulation",
                reg_description=(
                    "Establishes safety requirements for workplace facilities."
                ),
                certifier_org_name="Example Certification Services",
                inspection_date=date(2026, 9, 15),
                findings=[
                    FindingHistory(
                        finding_id=301,
                        finding=(
                            "The emergency exit was partially obstructed by "
                            "stored materials."
                        ),
                        rule_index="4.2",
                        rule_title="Emergency exits",
                        rule_description=(
                            "Emergency exits must remain clear and accessible."
                        ),
                    ),
                    FindingHistory(
                        finding_id=302,
                        finding=(
                            "The inspection record for one fire extinguisher "
                            "was not available."
                        ),
                        rule_index="5.1",
                        rule_title=None,
                        rule_description=(
                            "Fire-protection equipment must be inspected and "
                            "documented at the required intervals."
                        ),
                    ),
                ],
            )
        ],
    )

    queries = build_site_analysis_query_embedding_input(
        sample_site,
        sample_site_history,
    )

    for finding_id, query in queries.items():
        print(f"Finding ID: {finding_id}")
        print(query)
        print("-" * 80)
