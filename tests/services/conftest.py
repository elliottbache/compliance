from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.llm.schemas import (
    EvidenceRef,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)


@pytest.fixture
def evidence_ref_factory():
    def _build(**overrides) -> EvidenceRef:
        data = {
            "cert_id": 100,
            "reg_title": "USDA Organic",
            "finding_id": 1,
            "rule_index": "7 CFR 205.201",
            "inspection_date": date(2024, 1, 10),
            "support_text": "Inspector noted labeling issue.",
        }
        data.update(overrides)
        return EvidenceRef(**data)

    return _build


@pytest.fixture
def site_analysis_factory(evidence_ref_factory):
    def _build(**overrides) -> SiteAnalysis:
        recurring_evidence_1 = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Recurring evidence 1.",
        )
        recurring_evidence_2 = evidence_ref_factory(
            cert_id=100,
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="Recurring evidence 2.",
        )
        missing_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="Missing info evidence.",
        )
        human_review_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Needs review evidence.",
        )
        suggestion_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Suggestion evidence.",
        )

        data = {
            "site_id": 71,
            "inspection_count": 1,
            "executive_summary": "Short summary.",
            "recurring_issues": [
                RecurringIssueItem(
                    item="Repeated labeling issue",
                    confidence_note="Seen across inspections.",
                    evidence=[recurring_evidence_1, recurring_evidence_2],
                )
            ],
            "missing_information": [
                MissingInfoItem(
                    item="Missing attachments",
                    why_missing_matters="They would confirm follow-up details.",
                    evidence=[missing_evidence],
                )
            ],
            "needs_human_review": [
                HumanReviewItem(
                    item="Inspector should review ambiguity",
                    evidence=[human_review_evidence],
                )
            ],
            "suggestions": [
                SuggestionItem(
                    item="Check labeling records",
                    basis="Prior labeling issue suggests targeted follow-up.",
                    evidence=[suggestion_evidence],
                )
            ],
        }
        data.update(overrides)
        return SiteAnalysis(**data)

    return _build


@pytest.fixture
def attachment_row_factory():
    def _build(**overrides):
        row = {
            "Attachment": SimpleNamespace(
                id=50,
                file_type="pdf",
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=date(2026, 4, 3),
                certification_id=100,
            ),
            "Certification": SimpleNamespace(
                site_id=71,
                id=100,
                regulation_id=5,
                inspection_date=date(2026, 4, 1),
            ),
            "Regulation": SimpleNamespace(
                id=5,
                title="USDA Organic",
            ),
            "Finding": SimpleNamespace(
                id=1,
                finding="Missing document",
            ),
            "FindingAttachment": MagicMock(),
            "Rule": SimpleNamespace(
                id=10,
                rule_index="7 CFR 205.201",
                title="Organic plan",
                description="Producer must maintain an organic system plan.",
            ),
        }
        row.update(overrides)
        return row

    return _build
