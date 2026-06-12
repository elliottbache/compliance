from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from compliance.api.schemas import FindingOut
from compliance.auth import authorization as authorization_module
from compliance.db.db_access import get_db
from compliance.db.models import Role
from compliance.llm.schemas import (
    EvidenceRef,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory
from fastapi.testclient import TestClient


@pytest.fixture
def client(main_module):
    return TestClient(main_module.app)


@pytest.fixture
def mock_db(main_module):
    mock = MagicMock()

    def _get_db():
        yield mock

    main_module.app.dependency_overrides[get_db] = _get_db
    yield mock
    main_module.app.dependency_overrides.clear()


@pytest.fixture
def id_record_factory():
    def _id_record(record_id):
        return SimpleNamespace(id=record_id)

    return _id_record


@pytest.fixture
def user_record_factory():
    def _user_record(**overrides):
        user = SimpleNamespace(
            id=10,
            full_name="Alice Inspector",
            email="alice@example.com",
            role=Role.VIEWER,
            is_active=True,
            created_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
        )
        user.__dict__.update(**overrides)
        return user

    return _user_record


@pytest.fixture
def admin_user_override(main_module, user_record_factory):
    def _get_active_user():
        return user_record_factory(role=Role.ADMIN)

    main_module.app.dependency_overrides[authorization_module.get_active_user] = (
        _get_active_user
    )
    yield
    main_module.app.dependency_overrides.pop(authorization_module.get_active_user, None)


@pytest.fixture
def viewer_user_override(main_module, user_record_factory):
    def _get_active_user():
        return user_record_factory(role=Role.VIEWER)

    main_module.app.dependency_overrides[authorization_module.get_active_user] = (
        _get_active_user
    )
    yield
    main_module.app.dependency_overrides.pop(authorization_module.get_active_user, None)


@pytest.fixture
def assert_archived_response():
    def _assert_archived_response(payload, reason=None):
        assert payload["archived_at"] is not None
        if reason is not None:
            assert payload["archive_reason"] == reason

    return _assert_archived_response


@pytest.fixture
def assert_restored_response():
    def _assert_restored_response(payload):
        assert payload["archived_at"] is None
        assert payload["archive_reason"] is None

    return _assert_restored_response


@pytest.fixture
def site_factory():
    def _site(**overrides):
        site = SimpleNamespace(
            id=12,
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
            archived_at=None,
            archive_reason=None,
        )
        site.__dict__.update(**overrides)
        return site

    return _site


@pytest.fixture
def site_history_factory():
    def _site_history(**overrides):
        site_history = SiteHistory(
            site_id=101,
            inspection_count=2,
            latest_inspection_date=date(2023, 11, 5),
            certifications=[
                CertificationHistory(
                    cert_id=5001,
                    result="Pass",
                    resolution_date=date(2023, 10, 20),
                    reg_title="Fire Safety 2023",
                    reg_description="Standard fire safety regulations for commercial buildings.",
                    certifier_org_name="SafeCheck Inc.",
                    inspection_date=date(2023, 10, 15),
                    findings=[
                        FindingHistory(
                            finding_id=901,
                            finding="Extinguisher pressure low",
                            rule_index="FS-101",
                            rule_title="Equipment Maintenance",
                            rule_description="Extinguishers must be within safe pressure limits.",
                        )
                    ],
                ),
                CertificationHistory(
                    cert_id=5002,
                    result=None,
                    resolution_date=None,
                    reg_title="Electrical Safety",
                    reg_description="General electrical standards.",
                    certifier_org_name="VoltGuard",
                    inspection_date=date(2023, 11, 5),
                    findings=[],
                ),
            ],
        )
        site_history.__dict__.update(**overrides)
        return site_history

    return _site_history


@pytest.fixture
def site_analysis_factory():
    def _site_analysis(**overrides):
        evidence = EvidenceRef(
            cert_id=5001,
            reg_title="Fire Safety 2023",
            finding_id=901,
            rule_index="FS-101",
            inspection_date=date(2023, 10, 15),
            support_text="Extinguisher pressure low.",
        )
        site_analysis = SiteAnalysis(
            site_id=101,
            inspection_count=2,
            executive_summary="Prior inspections show one extinguisher issue.",
            recurring_issues=[
                RecurringIssueItem(
                    item="Repeated safety documentation issue",
                    confidence_note="Supported by inspection evidence.",
                    evidence=[evidence, evidence],
                )
            ],
            missing_information=[
                MissingInfoItem(
                    item="Corrective action records",
                    why_missing_matters="They would confirm follow-up.",
                    evidence=[evidence],
                )
            ],
            needs_human_review=[
                HumanReviewItem(
                    item="Review extinguisher maintenance context",
                    evidence=[evidence],
                )
            ],
            suggestions=[
                SuggestionItem(
                    item="Review fire safety records before visiting",
                    basis="Prior inspection mentioned extinguisher pressure.",
                    evidence=[evidence],
                )
            ],
        )
        return site_analysis.model_copy(update=overrides)

    return _site_analysis


@pytest.fixture
def certifications_factory():
    def _certifications(count=1, **overrides):
        certifications = []
        for i in range(count):
            cert = SimpleNamespace(
                id=100 + i,
                certifier_id=200,
                regulation_id=300,
                site_id=12,
                result="Pass",
                inspection_date=date(2023, 10, 15),
                resolution_date=date(2023, 10, 20),
                archived_at=None,
                archive_reason=None,
            )
            cert.__dict__.update(**overrides)
            certifications.append(cert)
        return certifications

    return _certifications


@pytest.fixture
def client_record_factory():
    def _client_record(**overrides):
        client_record = SimpleNamespace(
            nif="A1234567B",
            company_name="Acme Corp",
            contact_name="John Doe",
            email="john.doe@acme.com",
            telephone=5550123,
            archived_at=None,
            archive_reason=None,
        )
        client_record.__dict__.update(**overrides)
        return client_record

    return _client_record


@pytest.fixture
def certifier_record_factory():
    def _certifier_record(**overrides):
        certifier_record = SimpleNamespace(
            id=10,
            organization_name="SafeCheck Inc.",
            archived_at=None,
            archive_reason=None,
        )
        certifier_record.__dict__.update(**overrides)
        return certifier_record

    return _certifier_record


@pytest.fixture
def rule_record_factory():
    def _rule_record(**overrides):
        rule_record = SimpleNamespace(
            id=20,
            regulation_id=3,
            rule_index="FS-101",
            title="Equipment Maintenance",
            description="Equipment must be maintained.",
            archived_at=None,
            archive_reason=None,
        )
        rule_record.__dict__.update(**overrides)
        return rule_record

    return _rule_record


@pytest.fixture
def regulation_record_factory():
    def _regulation_record(**overrides):
        regulation_record = SimpleNamespace(
            id=3,
            title="Fire Safety 2026",
            description="Fire safety requirements for commercial sites.",
            published_date=date(2026, 1, 15),
            archived_at=None,
            archive_reason=None,
        )
        regulation_record.__dict__.update(**overrides)
        return regulation_record

    return _regulation_record


@pytest.fixture
def attachment_factory():
    def _attachment(**overrides):
        attachment = {
            "id": 50,
            "file_name": "evidence",
            "file_path": "dummy/evidence.pdf",
            "description": "Inspection evidence",
            "uploaded_at": datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            "archived_at": None,
            "archive_reason": None,
            "certification_id": 100,
            "inspection_date": date(2026, 4, 1),
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "finding_links": [],
        }
        attachment.update(overrides)
        return attachment

    return _attachment


@pytest.fixture
def certification_attachments_factory(attachment_factory):
    def _certification_attachments(**overrides):
        certification_attachments = {
            "certification_id": 100,
            "attachments": [attachment_factory()],
        }
        certification_attachments.update(overrides)
        return certification_attachments

    return _certification_attachments


@pytest.fixture
def finding_factory():
    def _finding(**overrides):
        finding = {
            "finding_id": 1,
            "finding": "Missing document",
            "site_id": 12,
            "certification_id": 100,
            "certification_title": "USDA Organic",
            "certification_resolution_date": date(2026, 4, 15),
            "rule_id": 5,
            "rule_index": "7 CFR 205.201",
            "rule_title": "Organic plan",
            "rule_description": "Producer must maintain an organic system plan.",
            "archived_at": None,
            "archive_reason": None,
        }
        finding.update(overrides)
        return FindingOut.model_validate(finding)

    return _finding


@pytest.fixture
def attachment_create_factory():
    def _attachment_create(**overrides):
        attachment = {
            "file_name": "evidence",
            "certification_id": 100,
            "description": "Inspection evidence",
            "archived_at": None,
            "archive_reason": None,
            "finding_ids": [],
        }
        attachment.update(overrides)
        return attachment

    return _attachment_create
