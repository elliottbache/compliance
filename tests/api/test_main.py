from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from httpx import Request

from compliance.api.routers import (
    attachments as attachments_router,
)
from compliance.api.routers import (
    certifications as certifications_router,
)
from compliance.api.routers import (
    clients as clients_router,
)
from compliance.api.routers import (
    sites as sites_router,
)
from compliance.db.db_access import get_db
from compliance.llm.schemas import (
    EvidenceRef,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")

    return import_module("compliance.api.main")


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
                    result="Certified",
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
            # Base data for a single certification
            cert = SimpleNamespace(
                id=100 + i,
                certifier_id=200,
                regulation_id=300,
                site_id=12,
                result="Certified",
                inspection_date=date(2023, 10, 15),
                resolution_date=date(2023, 10, 20),
            )
            # Apply overrides to every item in the list
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
        )
        client_record.__dict__.update(**overrides)
        return client_record

    return _client_record


@pytest.fixture
def attachment_factory():
    def _attachment(**overrides):
        attachment = {
            "id": 50,
            "file_type": "pdf",
            "file_path": "dummy/evidence.pdf",
            "description": "Inspection evidence",
            "uploaded_at": date(2026, 4, 3),
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
def attachment_create_factory():
    def _attachment_create(**overrides):
        attachment = {
            "file_type": "pdf",
            "file_name": "evidence",
            "certification_id": 100,
            "description": "Inspection evidence",
            "finding_ids": [],
        }
        attachment.update(overrides)
        return attachment

    return _attachment_create


def site_history_row(**overrides):
    row = {
        "site_id": 71,
        "cert_id": 100,
        "result": "Pass",
        "resolution_date": None,
        "reg_title": "USDA Organic",
        "reg_description": "Organic certification",
        "certifier_org_name": "Org A",
        "inspection_date": date(2026, 4, 1),
        "finding_id": 1,
        "finding": "Missing document",
        "rule_index": "7 CFR 205.201",
        "rule_title": "Organic plan",
        "rule_description": "Producer must maintain an organic system plan.",
    }
    row.update(overrides)
    return row


class TestGetSiteByIdRoute:
    # TestClient
    def test_client_returns_site_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_factory
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return site_factory()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/12")

        assert response.status_code == 200
        assert response.json() == {
            "id": 12,
            "nif": "A1234567B",
            "city": "Madrid",
            "postal_code": 28013,
            "street": "Gran Via",
            "street_number": None,
            "suite": None,
            "address_info": "Main entrance",
        }

    def test_client_returns_404_when_site_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        fake_site = None

        def fake_get_site_by_id(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return fake_site

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999"}

    def test_client_returns_422_when_site_id_is_not_an_int(
        self, main_module, client, mock_db, monkeypatch, site_factory
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return site_factory()

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        response = client.get("/sites/not-an-int")

        assert response.status_code == 422

    # unittests
    def test_returns_site_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        site = SimpleNamespace(
            id=12,
            nif="A1234567B",
            city="Madrid",
            postal_code=28013,
            street="Gran Via",
            street_number=None,
            suite=None,
            address_info="Main entrance",
        )

        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        result = sites_router.get_site_by_id_route(12, fake_session)

        assert result == sites_router.SiteOut.model_validate(site)

    def test_returns_404_when_site_is_not_found(self, main_module, monkeypatch) -> None:
        def fake_get_site_by_id(site_id, session):
            return None

        monkeypatch.setattr(sites_router, "get_site_by_id", fake_get_site_by_id)

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999"

    def test_registers_site_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}"
        )

        assert route.response_model is sites_router.SiteOut


class TestGetCertificationByIdRoute:
    def test_client_returns_certification_json_when_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(certification_id, session):
            assert certification_id == 42
            assert session is mock_db
            return SimpleNamespace(
                id=42,
                certifier_id=7,
                regulation_id=3,
                site_id=12,
                result="Pass",
                inspection_date=date(2026, 4, 1),
                resolution_date=None,
            )

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        response = client.get("/certifications/42")

        assert response.status_code == 200
        assert response.json() == {
            "id": 42,
            "certifier_id": 7,
            "regulation_id": 3,
            "site_id": 12,
            "result": "Pass",
            "inspection_date": "2026-04-01",
            "resolution_date": None,
        }

    def test_client_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(certification_id, session):
            assert certification_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        response = client.get("/certifications/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "No certification for this id found: 999"}

    def test_client_returns_422_when_certification_id_is_not_an_int(self, client):
        response = client.get("/certifications/not-an-int")

        assert response.status_code == 422

    def test_returns_certification_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        certification = SimpleNamespace(
            id=42,
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
        )

        def fake_get_certification_by_id(certification_id, session):
            assert certification_id == 42
            assert session is fake_session
            return certification

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        result = certifications_router.get_certification_by_id_route(42, fake_session)

        assert result == certifications_router.CertificationOut.model_validate(
            certification
        )

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_certification_by_id(certification_id, session):
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certification_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No certification for this id found: 999"

    def test_registers_certification_output_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifications/{certification_id}"
        )

        assert route.response_model is certifications_router.CertificationOut


class TestGetSiteCertificationsRoute:
    # TestClient
    def test_client_returns_certifications_json_when_found(
        self, main_module, client, mock_db, monkeypatch, certifications_factory
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_certifications(site_id, session, limit, offset):
            assert site_id == 12
            assert session is mock_db
            return certifications_factory(2)

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        response = client.get("/sites/12/certifications")

        assert response.status_code == 200
        assert response.json() == {
            "site_id": 12,
            "certifications": [
                {
                    "id": 100,
                    "certifier_id": 200,
                    "regulation_id": 300,
                    "site_id": 12,
                    "result": "Certified",
                    "inspection_date": "2023-10-15",
                    "resolution_date": "2023-10-20",
                },
                {
                    "id": 101,
                    "certifier_id": 200,
                    "regulation_id": 300,
                    "site_id": 12,
                    "result": "Certified",
                    "inspection_date": "2023-10-15",
                    "resolution_date": "2023-10-20",
                },
            ],
        }

    def test_client_returns_empty_list_when_site_has_no_certifications(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_certifications(site_id, session, limit, offset):
            assert site_id == 999
            assert session is mock_db
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        response = client.get("/sites/999/certifications")

        assert response.status_code == 200
        assert response.json() == {"site_id": 999, "certifications": []}

    def test_client_returns_404_when_site_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )

        response = client.get("/sites/999/certifications")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999"}

    def test_client_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.get("/sites/not-an-int/certifications")

        assert response.status_code == 422

    # unittests
    def test_returns_certifications_for_site(self, main_module, monkeypatch) -> None:
        fake_session = object()
        certifications = [
            SimpleNamespace(
                id=42,
                certifier_id=7,
                regulation_id=3,
                site_id=12,
                result="Pass",
                inspection_date=date(2026, 4, 1),
                resolution_date=date(2026, 4, 15),
            ),
            SimpleNamespace(
                id=43,
                certifier_id=8,
                regulation_id=3,
                site_id=12,
                result="Fail",
                inspection_date=date(2026, 5, 1),
                resolution_date=None,
            ),
        ]

        def fake_get_site_certifications(site_id, session, limit, offset):
            assert site_id == 12
            assert session is fake_session
            assert limit is None
            assert offset == 0
            return certifications

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: SimpleNamespace(id=site_id),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(12, fake_session)

        assert result == sites_router.SiteCertificationsOut.model_validate(
            {"site_id": 12, "certifications": certifications}
        )

    def test_passes_limit_and_offset_to_service(self, main_module, monkeypatch) -> None:
        fake_session = object()

        def fake_get_site_certifications(site_id, session, limit, offset):
            assert site_id == 12
            assert session is fake_session
            assert limit == 10
            assert offset == 20
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: SimpleNamespace(id=site_id),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(
            12, fake_session, limit=10, offset=20
        )

        assert result == sites_router.SiteCertificationsOut(
            site_id=12, certifications=[]
        )

    def test_returns_empty_list_when_site_has_no_certifications(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_certifications(site_id, session, limit, offset):
            return []

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: SimpleNamespace(id=site_id),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_certifications",
            fake_get_site_certifications,
        )

        result = sites_router.get_site_certifications_route(999, object())

        assert result == sites_router.SiteCertificationsOut(
            site_id=999, certifications=[]
        )

    def test_returns_404_when_site_is_not_found(self, main_module, monkeypatch) -> None:
        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: None,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_certifications_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999"

    def test_registers_certification_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/certifications"
        )

        assert route.response_model is sites_router.SiteCertificationsOut


class TestGetSiteHistoryRoute:
    # TestClient
    def test_client_returns_site_history_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_history_factory
    ):
        def fake_get_site_history(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return site_history_factory()

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/12/history")

        assert response.status_code == 200
        assert response.json() == {
            "site_id": 101,
            "certifications": [
                {
                    "cert_id": 5001,
                    "result": "Certified",
                    "resolution_date": "2023-10-20",
                    "reg_title": "Fire Safety 2023",
                    "reg_description": "Standard fire safety regulations for commercial buildings.",
                    "certifier_org_name": "SafeCheck Inc.",
                    "inspection_date": "2023-10-15",
                    "findings": [
                        {
                            "finding_id": 901,
                            "finding": "Extinguisher pressure low",
                            "rule_index": "FS-101",
                            "rule_title": "Equipment Maintenance",
                            "rule_description": "Extinguishers must be within safe pressure limits.",
                        }
                    ],
                },
                {
                    "cert_id": 5002,
                    "result": None,
                    "resolution_date": None,
                    "reg_title": "Electrical Safety",
                    "reg_description": "General electrical standards.",
                    "certifier_org_name": "VoltGuard",
                    "inspection_date": "2023-11-05",
                    "findings": [],
                },
            ],
            "inspection_count": 2,
            "latest_inspection_date": "2023-11-05",
        }

    def test_client_returns_404_when_site_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        fake_site = None

        def fake_get_site_history(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return fake_site

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/999/history")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site history found for this id: 999"}

    def test_client_returns_422_when_site_id_is_not_an_int(
        self, main_module, client, mock_db, monkeypatch, site_history_factory
    ):
        def fake_get_site_history(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return site_history_factory()

        monkeypatch.setattr(sites_router, "get_site_history", fake_get_site_history)

        response = client.get("/sites/not-an-int/history")

        assert response.status_code == 422

    # unittests
    def test_returns_site_history_when_found(self, main_module, monkeypatch) -> None:
        fake_session = object()
        site_history = sites_router.SiteHistory(
            site_id=12,
            certifications=[],
            inspection_count=0,
            latest_inspection_date=None,
        )

        def fake_get_site_history(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site_history

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        result = sites_router.get_site_history_route(12, fake_session)

        assert result == site_history

    def test_returns_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_history(site_id, session):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_history_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site history found for this id: 999"

    def test_registers_site_history_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/history"
        )

        assert route.response_model is sites_router.SiteHistory


class TestCreateSiteAnalysisRoute:
    def test_client_returns_site_analysis_json_when_found(
        self, main_module, client, mock_db, monkeypatch, site_analysis_factory
    ):
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(site_id, session):
            assert site_id == 101
            assert session is mock_db
            return site_analysis

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        response = client.post("/sites/101/analysis")

        assert response.status_code == 200
        assert response.json()["site_id"] == 101
        assert (
            response.json()["executive_summary"]
            == "Prior inspections show one extinguisher issue."
        )

    def test_client_returns_404_when_site_history_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_create_site_analysis(site_id, session):
            assert site_id == 999
            assert session is mock_db
            raise HTTPException(status_code=404, detail="Site 999 not found.")

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        response = client.post("/sites/999/analysis")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site 999 not found."}

    def test_client_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.post("/sites/not-an-int/analysis")

        assert response.status_code == 422

    def test_delegates_to_create_site_analysis(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(site_id, session):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        result = sites_router.create_site_analysis_route(101, fake_session)

        assert result == site_analysis

    def test_registers_site_analysis_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/analysis"
        )

        assert route.response_model is sites_router.SiteAnalysis


class TestAnalyzeSiteReturnMarkdownRoute:
    def test_client_returns_rendered_markdown(
        self, main_module, client, mock_db, monkeypatch, site_analysis_factory
    ):
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(site_id, session):
            assert site_id == 101
            assert session is mock_db
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        response = client.post("/sites/101/analysis/markdown")

        assert response.status_code == 200
        assert response.text == "# Site Analysis\nMarkdown body."
        assert response.headers["content-type"].startswith("text/markdown")

    def test_client_returns_404_when_site_history_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_create_site_analysis(site_id, session):
            assert site_id == 999
            assert session is mock_db
            raise HTTPException(status_code=404, detail="Site 999 not found.")

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        response = client.post("/sites/999/analysis/markdown")

        assert response.status_code == 404
        assert response.json() == {"detail": "Site 999 not found."}

    def test_client_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.post("/sites/not-an-int/analysis/markdown")

        assert response.status_code == 422

    def test_returns_rendered_markdown(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(site_id, session):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        result = sites_router.create_site_analysis_markdown_route(101, fake_session)

        assert result.body == b"# Site Analysis\nMarkdown body."
        assert result.media_type == "text/markdown"

    def test_does_not_register_markdown_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/analysis/markdown"
        )

        assert route.response_model is None


class TestCreateSiteAnalysisMarkdownDownloadRoute:
    def test_returns_rendered_markdown_attachment(
        self, main_module, monkeypatch, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_analysis = site_analysis_factory()

        def fake_create_site_analysis(site_id, session):
            assert site_id == 101
            assert session is fake_session
            return site_analysis

        def fake_build_site_analysis_markdown(analysis):
            assert analysis is site_analysis
            return "# Site Analysis\nMarkdown body."

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )
        monkeypatch.setattr(
            sites_router,
            "build_site_analysis_markdown",
            fake_build_site_analysis_markdown,
        )

        result = sites_router.create_site_analysis_markdown_download_route(
            101, fake_session
        )

        assert result.body == b"# Site Analysis\nMarkdown body."
        assert result.media_type == "text/markdown"
        assert (
            result.headers["content-disposition"]
            == 'attachment; filename="site-101-analysis.md"'
        )

    def test_propagates_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_create_site_analysis(site_id, session):
            assert site_id == 999
            raise HTTPException(status_code=404, detail="Site 999 not found.")

        monkeypatch.setattr(
            sites_router,
            "_create_site_analysis",
            fake_create_site_analysis,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.create_site_analysis_markdown_download_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 999 not found."

    def test_does_not_register_download_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None)
            == "/sites/{site_id}/analysis/markdown/download"
        )

        assert route.response_model is None


class TestCreateSiteAnalysis:
    def test_returns_site_analysis_when_history_exists(
        self, main_module, monkeypatch, site_history_factory, site_analysis_factory
    ) -> None:
        fake_session = object()
        site_history = site_history_factory()
        site_analysis = site_analysis_factory()

        def fake_get_site_history(site_id, session):
            assert site_id == 101
            assert session is fake_session
            return site_history

        def fake_summarize_previous_visits(history):
            assert history is site_history
            return site_analysis

        def fake_validate_llm_references(analysis, history):
            assert analysis is site_analysis
            assert history is site_history
            return True

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )
        monkeypatch.setattr(
            sites_router,
            "validate_llm_references",
            fake_validate_llm_references,
        )

        result = sites_router._create_site_analysis(101, fake_session)

        assert result == site_analysis

    def test_returns_404_when_site_history_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_history(site_id, session):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 999 not found."

    @pytest.mark.parametrize(
        "exception_factory",
        [
            lambda main_module: sites_router.APIError(
                "API unavailable",
                request=Request("POST", "https://api.anthropic.com"),
                body=None,
            ),
            lambda main_module: sites_router.ValidationError.from_exception_data(
                "SiteAnalysis",
                [{"type": "missing", "loc": ("site_id",), "input": {}}],
            ),
            lambda main_module: sites_router.JSONDecodeError("Invalid JSON", "{", 0),
        ],
    )
    def test_returns_502_when_ai_analysis_fails(
        self, main_module, monkeypatch, site_history_factory, exception_factory
    ) -> None:
        site_history = site_history_factory()

        def fake_get_site_history(site_id, session):
            return site_history

        def fake_summarize_previous_visits(history):
            raise exception_factory(main_module)

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(101, object())

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail == "AI analysis failed for site 101."

    def test_returns_502_when_analysis_references_invalid_evidence(
        self, main_module, monkeypatch, site_history_factory, site_analysis_factory
    ) -> None:
        site_history = site_history_factory()
        site_analysis = site_analysis_factory()

        def fake_get_site_history(site_id, session):
            return site_history

        def fake_summarize_previous_visits(history):
            return False, "v-test", site_analysis

        def fake_validate_llm_references(analysis, history):
            return False

        monkeypatch.setattr(
            sites_router,
            "get_site_history",
            fake_get_site_history,
        )
        monkeypatch.setattr(
            sites_router,
            "summarize_previous_visits",
            fake_summarize_previous_visits,
        )
        monkeypatch.setattr(
            sites_router,
            "validate_llm_references",
            fake_validate_llm_references,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router._create_site_analysis(101, object())

        assert exc_info.value.status_code == 502
        assert (
            exc_info.value.detail == "LLM model returned invalid evidence for site 101."
        )


class TestGetSiteAttachmentsRoute:
    def test_client_returns_site_attachments_json_when_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        site_attachments = sites_router.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_by_id(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_attachments(site_id, session):
            assert site_id == 12
            assert session is mock_db
            return site_attachments

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/12/attachments")

        assert response.status_code == 200
        assert response.json() == {"site_id": 12, "attachments": []}

    def test_client_returns_empty_attachment_list_when_site_has_none(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return SimpleNamespace(id=site_id)

        def fake_get_site_attachments(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        response = client.get("/sites/999/attachments")

        assert response.status_code == 200
        assert response.json() == {"site_id": 999, "attachments": []}

    def test_client_returns_404_when_site_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_site_by_id(site_id, session):
            assert site_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            fake_get_site_by_id,
        )

        response = client.get("/sites/999/attachments")

        assert response.status_code == 404
        assert response.json() == {"detail": "No site for this id found: 999"}

    def test_client_returns_422_when_site_id_is_not_an_int(self, client):
        response = client.get("/sites/not-an-int/attachments")

        assert response.status_code == 422

    def test_returns_site_attachments_when_found(
        self, main_module, monkeypatch
    ) -> None:
        fake_session = object()
        site_attachments = sites_router.SiteAttachmentsOut(
            site_id=12,
            attachments=[],
        )

        def fake_get_site_attachments(site_id, session):
            assert site_id == 12
            assert session is fake_session
            return site_attachments

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: SimpleNamespace(id=site_id),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(12, fake_session)

        assert result == site_attachments

    def test_returns_empty_attachment_list_when_site_has_none(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_site_attachments(site_id, session):
            return None

        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: SimpleNamespace(id=site_id),
        )
        monkeypatch.setattr(
            sites_router,
            "get_site_attachments",
            fake_get_site_attachments,
        )

        result = sites_router.get_site_attachments_route(999, object())

        assert result == sites_router.SiteAttachmentsOut(site_id=999, attachments=[])

    def test_returns_404_when_site_is_not_found(self, main_module, monkeypatch) -> None:
        monkeypatch.setattr(
            sites_router,
            "get_site_by_id",
            lambda site_id, session: None,
        )

        with pytest.raises(HTTPException) as exc_info:
            sites_router.get_site_attachments_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No site for this id found: 999"

    def test_registers_site_attachments_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/sites/{site_id}/attachments"
        )

        assert route.response_model is sites_router.SiteAttachmentsOut


class TestGetCertificationAttachmentsByIdRoute:
    def test_client_returns_certification_attachments_json_when_found(
        self,
        main_module,
        client,
        mock_db,
        monkeypatch,
        certification_attachments_factory,
    ):
        def fake_get_certification_attachments_by_id(certification_id, session):
            assert certification_id == 100
            assert session is mock_db
            return certification_attachments_factory()

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        response = client.get("/certifications/100/attachments")

        assert response.status_code == 200
        assert response.json() == {
            "certification_id": 100,
            "attachments": [
                {
                    "id": 50,
                    "file_type": "pdf",
                    "file_path": "dummy/evidence.pdf",
                    "description": "Inspection evidence",
                    "uploaded_at": "2026-04-03",
                    "certification_id": 100,
                    "inspection_date": "2026-04-01",
                    "regulation_id": 5,
                    "regulation_title": "USDA Organic",
                    "finding_links": [],
                }
            ],
        }

    def test_client_returns_empty_attachment_list_when_certification_has_none(
        self,
        main_module,
        client,
        mock_db,
        monkeypatch,
        certification_attachments_factory,
    ):
        def fake_get_certification_attachments_by_id(certification_id, session):
            assert certification_id == 100
            assert session is mock_db
            return certification_attachments_factory(attachments=[])

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        response = client.get("/certifications/100/attachments")

        assert response.status_code == 200
        assert response.json() == {"certification_id": 100, "attachments": []}

    def test_client_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_certification_attachments_by_id(certification_id, session):
            assert certification_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        response = client.get("/certifications/999/attachments")

        assert response.status_code == 404
        assert response.json() == {"detail": "No certification for this id found: 999"}

    def test_client_returns_422_when_certification_id_is_not_an_int(self, client):
        response = client.get("/certifications/not-an-int/attachments")

        assert response.status_code == 422

    def test_returns_certification_attachments_when_found(
        self,
        main_module,
        monkeypatch,
        certification_attachments_factory,
    ) -> None:
        fake_session = object()

        def fake_get_certification_attachments_by_id(certification_id, session):
            assert certification_id == 100
            assert session is fake_session
            return certification_attachments_factory()

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        result = certifications_router.get_certification_attachments_by_id_route(
            100, fake_session
        )

        assert (
            result
            == certifications_router.CertificationAttachmentsOut.model_validate(
                certification_attachments_factory()
            )
        )

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_certification_attachments_by_id(certification_id, session):
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certification_attachments_by_id_route(
                999, object()
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No certification for this id found: 999"

    def test_registers_certification_attachments_response_model(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None)
            == "/certifications/{certification_id}/attachments"
        )

        assert route.response_model is certifications_router.CertificationAttachmentsOut


class TestGetAttachmentByIdRoute:
    def test_client_returns_attachment_without_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session):
            assert attachment_id == 50
            assert session is mock_db
            return attachment_factory()

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/50")

        assert response.status_code == 200
        assert response.json() == {
            "id": 50,
            "file_type": "pdf",
            "file_path": "dummy/evidence.pdf",
            "description": "Inspection evidence",
            "uploaded_at": "2026-04-03",
            "certification_id": 100,
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
            "finding_links": [],
        }

    def test_client_returns_attachment_with_two_findings(
        self, main_module, client, mock_db, monkeypatch, attachment_factory
    ):
        def fake_get_attachment_by_id(attachment_id, session):
            assert attachment_id == 50
            assert session is mock_db
            return attachment_factory(
                finding_links=[
                    {
                        "finding_id": 1,
                        "finding": "Missing document",
                        "rule_index": "7 CFR 205.201",
                        "rule_title": "Organic plan",
                        "rule_description": "Producer must maintain an organic system plan.",
                    },
                    {
                        "finding_id": 2,
                        "finding": "Incomplete record",
                        "rule_index": "7 CFR 205.202",
                        "rule_title": "Land requirements",
                        "rule_description": "Land must meet organic requirements.",
                    },
                ]
            )

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/50")

        assert response.status_code == 200
        assert [
            finding["finding_id"] for finding in response.json()["finding_links"]
        ] == [
            1,
            2,
        ]

    def test_client_returns_404_when_attachment_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_attachment_by_id(attachment_id, session):
            assert attachment_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        response = client.get("/attachments/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Attachment 999 not found."}

    def test_client_returns_422_when_attachment_id_is_not_an_int(self, client):
        response = client.get("/attachments/not-an-int")

        assert response.status_code == 422

    def test_returns_attachment_when_found(
        self, main_module, monkeypatch, attachment_factory
    ) -> None:
        fake_session = object()

        def fake_get_attachment_by_id(attachment_id, session):
            assert attachment_id == 50
            assert session is fake_session
            return attachment_factory()

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        result = attachments_router.get_attachment_by_id_route(50, fake_session)

        assert result == attachments_router.AttachmentWithContextOut.model_validate(
            attachment_factory()
        )

    def test_returns_404_when_attachment_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_attachment_by_id(attachment_id, session):
            return None

        monkeypatch.setattr(
            attachments_router, "get_attachment_by_id", fake_get_attachment_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.get_attachment_by_id_route(999, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Attachment 999 not found."

    def test_registers_attachment_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/attachments/{attachment_id}"
        )

        assert route.response_model is attachments_router.AttachmentWithContextOut


class TestPostNewAttachmentRoute:
    def test_client_returns_attachment_json_when_created(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        new_attachment = attachments_router.AttachmentOut.model_validate(
            {
                **attachment_create_factory(),
                "id": 50,
                "uploaded_at": date(2026, 4, 3),
                "inspection_date": date(2026, 4, 1),
                "regulation_id": 5,
                "regulation_title": "USDA Organic",
            }
        )

        def fake_post_new_attachment(attachment, session):
            assert attachment.file_type == "pdf"
            assert attachment.file_name == "evidence"
            assert attachment.certification_id == 100
            assert session is mock_db
            return new_attachment

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 201
        assert response.json() == {
            "file_type": "pdf",
            "file_name": "evidence",
            "certification_id": 100,
            "description": "Inspection evidence",
            "finding_ids": [],
            "id": 50,
            "uploaded_at": "2026-04-03",
            "inspection_date": "2026-04-01",
            "regulation_id": 5,
            "regulation_title": "USDA Organic",
        }

    def test_client_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert attachment.certification_id == 100
            assert session is mock_db
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 404
        assert response.json() == {"detail": "Certification 100 does not exist."}

    def test_client_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert attachment.finding_ids == [7]
            assert session is mock_db
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post(
            "/attachments", json=attachment_create_factory(finding_ids=[7])
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": "Finding 7 does not belong to certification 100."
        }

    def test_client_returns_409_when_attachment_conflicts(
        self, main_module, client, mock_db, monkeypatch, attachment_create_factory
    ):
        def fake_post_new_attachment(attachment, session):
            assert session is mock_db
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        response = client.post("/attachments", json=attachment_create_factory())

        assert response.status_code == 409
        assert response.json() == {"detail": "Attachment could not be created."}

    def test_client_returns_422_when_attachment_is_invalid(self, client):
        response = client.post("/attachments", json={"file_type": "pdf"})

        assert response.status_code == 422

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentCertificationNotFoundError(
                "Certification 100 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification 100 does not exist."

    def test_returns_404_when_finding_is_not_found(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentFindingNotFoundError(
                "Finding 7 does not exist."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Finding 7 does not exist."

    def test_returns_422_when_finding_belongs_to_another_certification(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory(finding_ids=[7])
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentFindingCertificationMismatchError(
                "Finding 7 does not belong to certification 100."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 422
        assert (
            exc_info.value.detail == "Finding 7 does not belong to certification 100."
        )

    def test_returns_409_when_attachment_conflicts(
        self, main_module, monkeypatch, attachment_create_factory
    ) -> None:
        attachment = attachments_router.AttachmentCreate.model_validate(
            attachment_create_factory()
        )

        def fake_post_new_attachment(attachment_info, session):
            raise attachments_router.AttachmentConflictError(
                "Attachment could not be created."
            )

        monkeypatch.setattr(
            attachments_router,
            "post_new_attachment",
            fake_post_new_attachment,
        )

        with pytest.raises(HTTPException) as exc_info:
            attachments_router.post_new_attachment_route(attachment, object())

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Attachment could not be created."


class TestPostNewClientRoute:
    # TestClient
    def test_client_returns_client_json_when_found(
        self, main_module, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_post_new_client(client_record, session):
            assert client_record.nif == "A1234567B"
            assert client_record.company_name == "Acme Corp"
            assert session is mock_db
            return client_record_factory()

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        response = client.post("/clients", json=vars(client_record_factory()))

        assert response.status_code == 201
        assert response.json() == {
            "nif": "A1234567B",
            "company_name": "Acme Corp",
            "contact_name": "John Doe",
            "email": "john.doe@acme.com",
            "telephone": 5550123,
        }

    def test_client_returns_409_when_client_already_exists(
        self, main_module, client, mock_db, monkeypatch, client_record_factory
    ):
        fake_site = None

        def fake_post_new_client(client_record, session):
            assert session is mock_db
            return fake_site

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        response = client.post("/clients", json=vars(client_record_factory()))

        assert response.status_code == 409
        assert response.json()["detail"].startswith("Client was not added: ")

    def test_client_returns_422_when_client_is_invalid(
        self, client, client_record_factory
    ):
        response = client.post("/clients", json=vars(client_record_factory(nif=12)))

        assert response.status_code == 422

    # unittests
    def test_returns_created_client(self, main_module, monkeypatch) -> None:
        fake_session = object()
        client = clients_router.ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(client_info, session):
            assert client_info is client
            assert session is fake_session
            return client

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        result = clients_router.post_new_client_route(client, fake_session)

        assert result == client

    def test_returns_409_when_client_is_not_created(
        self, main_module, monkeypatch
    ) -> None:
        client = clients_router.ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(client_info, session):
            return None

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(client, object())

        assert exc_info.value.status_code == 409
        assert "Client was not added" in exc_info.value.detail

    def test_registers_client_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients"
        )

        assert route.response_model is clients_router.ClientInOut
        assert route.status_code == 201
