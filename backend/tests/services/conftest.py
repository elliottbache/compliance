from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from compliance.db.models import (
    Attachment,
    Certification,
    Certifier,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
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
def attachment_out_factory():
    def _build(**overrides):
        row = {
            "Attachment": SimpleNamespace(
                id=50,
                file_type="pdf",
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                archived_at=None,
                archive_reason=None,
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


@pytest.fixture
def certification_row_factory():
    def _build(**overrides):
        certification = Certification(
            id=42,
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
        )
        for key, value in overrides.items():
            setattr(certification, key, value)
        return certification

    return _build


@pytest.fixture
def certifier_row_factory():
    def _build(**overrides):
        certifier = Certifier(id=7, organization_name="SafeCheck Inc.")
        for key, value in overrides.items():
            setattr(certifier, key, value)
        return certifier

    return _build


@pytest.fixture
def site_row_factory():
    def _site(**overrides) -> Site:
        site = Site(
            id=12,
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
        )
        for key, value in overrides.items():
            setattr(site, key, value)
        return site

    return _site


@pytest.fixture
def rule_row_factory():
    def _rule(**overrides) -> Rule:
        rule = Rule(
            id=5,
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
        )
        for key, value in overrides.items():
            setattr(rule, key, value)
        return rule

    return _rule


@pytest.fixture
def regulation_row_factory():
    def _regulation(**overrides) -> Regulation:
        regulation = Regulation(
            id=3,
            title="Fire Safety 2026",
            description="Fire safety requirements for commercial sites.",
            published_date=date(2026, 1, 15),
        )
        for key, value in overrides.items():
            setattr(regulation, key, value)
        return regulation

    return _regulation


@pytest.fixture
def finding_row_factory():
    def _finding(**overrides) -> Finding:
        finding = Finding(
            id=1,
            certification_id=42,
            rule_id=5,
            finding="Missing document",
        )
        for key, value in overrides.items():
            setattr(finding, key, value)
        return finding

    return _finding


@pytest.fixture
def client_row_factory():
    def _client(**overrides) -> Client:
        client = Client(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )
        for key, value in overrides.items():
            setattr(client, key, value)
        return client

    return _client


@pytest.fixture
def attachment_row_factory():
    def _attachment(**overrides) -> Attachment:
        attachment = Attachment(
            id=50,
            file_type="pdf",
            certification_id=42,
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
        )
        for key, value in overrides.items():
            setattr(attachment, key, value)
        return attachment

    return _attachment


@pytest.fixture
def finding_attachment_row_factory():
    def _finding_attachment(**overrides) -> FindingAttachment:
        finding_attachment = FindingAttachment(
            finding_id=1, attachment_id=50, certification_id=42
        )
        for key, value in overrides.items():
            setattr(finding_attachment, key, value)
        return finding_attachment

    return _finding_attachment


@pytest.fixture
def db_factory(
    sqlite_session,
    attachment_row_factory,
    certification_row_factory,
    certifier_row_factory,
    client_row_factory,
    site_row_factory,
    regulation_row_factory,
    finding_attachment_row_factory,
    finding_row_factory,
    rule_row_factory,
):
    def _make(
        *,
        attachment_overrides=None,
        certification_overrides=None,
        certifier_overrides=None,
        client_overrides=None,
        regulation_overrides=None,
        site_overrides=None,
        finding_overrides=None,
        finding_attachment_overrides=None,
        rule_overrides=None,
    ):
        attachment = attachment_row_factory(
            **(attachment_overrides or {}),
        )
        certification = certification_row_factory(
            **(certification_overrides or {}),
        )
        certifier = certifier_row_factory(**(certifier_overrides or {}))
        client = client_row_factory(**(client_overrides or {}))
        regulation = regulation_row_factory(**(regulation_overrides or {}))
        site = site_row_factory(**(site_overrides or {}))
        finding_attachment = finding_attachment_row_factory(
            **(finding_attachment_overrides or {})
        )
        finding = finding_row_factory(**(finding_overrides or {}))
        rule = rule_row_factory(**(rule_overrides or {}))

        sqlite_session.add_all(
            [
                attachment,
                certification,
                certifier,
                client,
                regulation,
                site,
                finding_attachment,
                finding,
                rule,
            ]
        )
        sqlite_session.commit()

        return {
            "attachment": attachment,
            "certification": certification,
            "certifier": certifier,
            "client": client,
            "regulation": regulation,
            "site": site,
            "finding_attachment": finding_attachment,
            "finding": finding,
            "rule": rule,
        }

    return _make
