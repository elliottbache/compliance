from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from compliance.api.routers import certifications as certifications_router


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
