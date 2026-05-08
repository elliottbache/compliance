from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from compliance.api.routers import certifications as certifications_router


class TestGetCertificationsRoute:
    def test_client_returns_certifications_json(
        self, client, mock_db, monkeypatch, certifications_factory
    ):
        def fake_get_certifications(
            session, *, site_id, open_only, limit, offset, include_archived=False
        ):
            assert session is mock_db
            assert site_id is None
            assert open_only is False
            assert limit == 2
            assert offset == 1
            assert include_archived is True
            return [
                certifications_router.CertificationOut.model_validate(certification)
                for certification in certifications_factory(2, result="Pass")
            ]

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        response = client.get("/certifications?limit=2&offset=1&include_archived=true")

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 100,
                "certifier_id": 200,
                "regulation_id": 300,
                "site_id": 12,
                "result": "Pass",
                "inspection_date": "2023-10-15",
                "resolution_date": "2023-10-20",
                "archived_at": None,
                "archive_reason": None,
            },
            {
                "id": 101,
                "certifier_id": 200,
                "regulation_id": 300,
                "site_id": 12,
                "result": "Pass",
                "inspection_date": "2023-10-15",
                "resolution_date": "2023-10-20",
                "archived_at": None,
                "archive_reason": None,
            },
        ]

    def test_client_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/certifications?limit=0")

        assert response.status_code == 422

    def test_returns_certifications(self, monkeypatch, certifications_factory) -> None:
        fake_session = object()
        expected_certifications = [
            certifications_router.CertificationOut.model_validate(certification)
            for certification in certifications_factory(1, result="Pass")
        ]

        def fake_get_certifications(
            session, *, site_id, open_only, limit, offset, include_archived=False
        ):
            assert session is fake_session
            assert site_id == 12
            assert open_only is True
            assert limit == 10
            assert offset == 5
            return expected_certifications

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        result = certifications_router.get_certifications_route(
            fake_session, site_id=12, open_only=True, limit=10, offset=5
        )

        assert result == expected_certifications

    def test_returns_404_when_site_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_certifications(
            session, *, site_id, open_only, limit, offset, include_archived=False
        ):
            assert site_id == 999
            return None

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certifications_route(
                object(), site_id=999, open_only=False, limit=None, offset=0
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site does not exist: 999"

    def test_registers_certification_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifications"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[certifications_router.CertificationOut]


class TestGetCertificationByIdRoute:
    def test_client_returns_certification_json_when_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
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
                archived_at=None,
                archive_reason=None,
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
            "archived_at": None,
            "archive_reason": None,
        }

    def test_client_returns_404_when_certification_is_not_found(
        self, main_module, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
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
            archived_at=None,
            archive_reason=None,
        )

        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert certification_id == 42
            assert session is fake_session
            return certification

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        result = certifications_router.get_certification_by_id_route(fake_session, 42)

        assert result == certifications_router.CertificationOut.model_validate(
            certification
        )

    def test_returns_404_when_certification_is_not_found(
        self, main_module, monkeypatch
    ) -> None:
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certification_by_id_route(object(), 999)

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
        def fake_get_certification_attachments_by_id(
            session, certification_id, *, include_archived=False
        ):
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
                    "uploaded_at": "2026-04-03T09:30:00Z",
                    "certification_id": 100,
                    "inspection_date": "2026-04-01",
                    "regulation_id": 5,
                    "regulation_title": "USDA Organic",
                    "finding_links": [],
                    "archived_at": None,
                    "archive_reason": None,
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
        def fake_get_certification_attachments_by_id(
            session, certification_id, *, include_archived=False
        ):
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
        def fake_get_certification_attachments_by_id(
            session, certification_id, *, include_archived=False
        ):
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

        def fake_get_certification_attachments_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert certification_id == 100
            assert session is fake_session
            return certification_attachments_factory()

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        result = certifications_router.get_certification_attachments_by_id_route(
            fake_session, 100
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
        def fake_get_certification_attachments_by_id(
            session, certification_id, *, include_archived=False
        ):
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_attachments_by_id",
            fake_get_certification_attachments_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certification_attachments_by_id_route(
                object(), 999
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


class TestGetCertificationFindingsRoute:
    def test_client_returns_findings_json_when_certification_is_found(
        self, client, mock_db, monkeypatch, finding_factory
    ):
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert certification_id == 100
            assert session is mock_db
            return SimpleNamespace(id=100)

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            assert site_id is None
            assert certification_id == 100
            assert rule_id is None
            assert attachment_id is None
            assert open_only is False
            return [finding_factory()]

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )
        monkeypatch.setattr(certifications_router, "get_findings", fake_get_findings)

        response = client.get("/certifications/100/findings")

        assert response.status_code == 200
        assert response.json() == [
            {
                "finding_id": 1,
                "finding": "Missing document",
                "site_id": 12,
                "certification_id": 100,
                "certification_title": "USDA Organic",
                "certification_resolution_date": "2026-04-15",
                "rule_id": 5,
                "rule_index": "7 CFR 205.201",
                "rule_title": "Organic plan",
                "rule_description": "Producer must maintain an organic system plan.",
                "attachments": [],
                "archived_at": None,
                "archive_reason": None,
            }
        ]

    def test_client_returns_empty_findings_json_when_certification_has_none(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert session is mock_db
            return SimpleNamespace(id=certification_id)

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is mock_db
            return []

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )
        monkeypatch.setattr(certifications_router, "get_findings", fake_get_findings)

        response = client.get("/certifications/100/findings")

        assert response.status_code == 200
        assert response.json() == []

    def test_client_returns_404_when_certification_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert certification_id == 999
            assert session is mock_db
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        response = client.get("/certifications/999/findings")

        assert response.status_code == 404
        assert response.json() == {"detail": "No certification for this id found: 999"}

    def test_client_returns_422_when_certification_id_is_not_an_int(self, client):
        response = client.get("/certifications/not-an-int/findings")

        assert response.status_code == 422

    def test_returns_findings_when_certification_is_found(
        self, monkeypatch, finding_factory
    ) -> None:
        fake_session = object()
        expected_findings = [finding_factory()]

        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            assert certification_id == 100
            assert session is fake_session
            return SimpleNamespace(id=100)

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            assert session is fake_session
            assert site_id is None
            assert certification_id == 100
            assert rule_id is None
            assert attachment_id is None
            assert open_only is False
            return expected_findings

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )
        monkeypatch.setattr(certifications_router, "get_findings", fake_get_findings)

        result = certifications_router.get_certification_findings_route(
            fake_session, 100
        )

        assert result == expected_findings

    def test_returns_empty_list_when_certification_has_no_findings(
        self, monkeypatch
    ) -> None:
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            return SimpleNamespace(id=certification_id)

        def fake_get_findings(
            session,
            *,
            site_id,
            certification_id,
            rule_id,
            attachment_id,
            open_only,
            include_archived=False,
        ):
            return []

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )
        monkeypatch.setattr(certifications_router, "get_findings", fake_get_findings)

        result = certifications_router.get_certification_findings_route(object(), 100)

        assert result == []

    def test_returns_404_when_certification_is_not_found(self, monkeypatch) -> None:
        def fake_get_certification_by_id(
            session, certification_id, *, include_archived=False
        ):
            return None

        monkeypatch.setattr(
            certifications_router,
            "get_certification_by_id",
            fake_get_certification_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certification_findings_route(object(), 999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "No certification for this id found: 999"

    def test_registers_certification_findings_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None)
            == "/certifications/{certification_id}/findings"
        )

        assert route.response_model == list[certifications_router.FindingOut]


class TestPostNewCertificationRoute:
    def test_client_returns_created_certification_json(
        self, client, mock_db, monkeypatch
    ):
        created_certification = SimpleNamespace(
            id=42,
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_new_certification(session, certification):
            assert certification.certifier_id == 7
            assert certification.regulation_id == 3
            assert certification.site_id == 12
            assert session is mock_db
            return created_certification

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        response = client.post(
            "/certifications",
            json={
                "certifier_id": 7,
                "regulation_id": 3,
                "site_id": 12,
                "result": "Pass",
                "inspection_date": "2026-04-01",
                "resolution_date": None,
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 42,
            "certifier_id": 7,
            "regulation_id": 3,
            "site_id": 12,
            "result": "Pass",
            "inspection_date": "2026-04-01",
            "resolution_date": None,
            "archived_at": None,
            "archive_reason": None,
        }

    def test_client_returns_409_when_certification_conflicts(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_certification(session, certification):
            assert session is mock_db
            raise certifications_router.CertificationConflictError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        response = client.post(
            "/certifications",
            json={
                "certifier_id": 7,
                "regulation_id": 3,
                "site_id": 12,
                "result": "Pass",
                "inspection_date": "2026-04-01",
                "resolution_date": None,
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"].startswith("Certification was not added: ")

    def test_client_returns_422_when_certification_result_is_invalid(self, client):
        response = client.post(
            "/certifications",
            json={
                "certifier_id": 7,
                "regulation_id": 3,
                "site_id": 12,
                "result": "Certified",
            },
        )

        assert response.status_code == 422

    def test_returns_created_certification(self, monkeypatch) -> None:
        fake_session = object()
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
            archived_at=None,
            archive_reason=None,
        )
        created_certification = SimpleNamespace(
            id=42,
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=None,
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_new_certification(session, certification_info):
            assert certification_info is certification
            assert session is fake_session
            return created_certification

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        result = certifications_router.post_new_certification_route(
            fake_session, certification
        )

        assert result == certifications_router.CertificationOut.model_validate(
            created_certification
        )

    def test_returns_404_when_certifier_does_not_exist(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationCertifierNotFoundError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(object(), certification)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certifier 7 does not exist."

    def test_returns_404_when_regulation_does_not_exist(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationRegulationNotFoundError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(object(), certification)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Regulation 3 does not exist."

    def test_returns_404_when_site_does_not_exist(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationSiteNotFoundError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(object(), certification)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 12 does not exist."

    def test_returns_409_when_certification_conflicts(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationConflictError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(object(), certification)

        assert exc_info.value.status_code == 409
        assert "Certification was not added" in exc_info.value.detail

    def test_registers_certification_create_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifications"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is certifications_router.CertificationOut
        assert route.status_code == 201


class TestPostCertificationArchivedByIdRoute:
    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected = certifications_router.CertificationOut(
            id=100,
            certifier_id=10,
            regulation_id=5,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=date(2026, 4, 15),
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_certification_archived_by_id(
            session, certification_id, *, archive_request
        ):
            assert session is fake_session
            assert certification_id == 100
            assert archive_request == certifications_router.ArchiveRequest()
            return expected

        monkeypatch.setattr(
            certifications_router,
            "post_certification_archived_by_id",
            fake_post_certification_archived_by_id,
        )

        result = certifications_router.post_certification_archived_by_id_route(
            fake_session, 100
        )

        assert result == expected

    def test_returns_404_when_certification_does_not_exist(self, monkeypatch) -> None:
        def fake_post_certification_archived_by_id(
            session, certification_id, *, archive_request
        ):
            return None

        monkeypatch.setattr(
            certifications_router,
            "post_certification_archived_by_id",
            fake_post_certification_archived_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_certification_archived_by_id_route(object(), 100)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification does not exist: 100."


class TestPostCertificationRestoredByIdRoute:
    def test_returns_restored_certification(self, monkeypatch) -> None:
        fake_session = object()
        expected = certifications_router.CertificationOut(
            id=100,
            certifier_id=10,
            regulation_id=5,
            site_id=12,
            result="Pass",
            inspection_date=date(2026, 4, 1),
            resolution_date=date(2026, 4, 15),
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_certification_restored_by_id(session, certification_id):
            assert session is fake_session
            assert certification_id == 100
            return expected

        monkeypatch.setattr(
            certifications_router,
            "post_certification_restored_by_id",
            fake_post_certification_restored_by_id,
        )

        result = certifications_router.post_certification_restored_by_id_route(
            fake_session, 100
        )

        assert result == expected

    def test_returns_404_when_certification_does_not_exist(self, monkeypatch) -> None:
        def fake_post_certification_restored_by_id(session, certification_id):
            return None

        monkeypatch.setattr(
            certifications_router,
            "post_certification_restored_by_id",
            fake_post_certification_restored_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_certification_restored_by_id_route(object(), 100)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certification does not exist: 100."
