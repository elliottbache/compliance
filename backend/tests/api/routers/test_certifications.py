from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from compliance.api.routers import certifications as certifications_router
from fastapi import HTTPException


@pytest.mark.usefixtures("viewer_user_override")
class TestGetCertificationsRouteClient:
    def test_route_returns_certifications_json(
        self, client, mock_db, monkeypatch, certifications_factory
    ):
        def fake_get_certifications(
            session,
            *,
            site_id,
            open_only,
            limit,
            offset,
            include_archived=False,
            inspector_id=None,
        ):
            assert session is mock_db
            assert site_id is None
            assert open_only is False
            assert limit == 2
            assert offset == 1
            assert include_archived is True
            assert inspector_id is None
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
                "inspector_id": None,
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
                "inspector_id": None,
                "result": "Pass",
                "inspection_date": "2023-10-15",
                "resolution_date": "2023-10-20",
                "archived_at": None,
                "archive_reason": None,
            },
        ]

    def test_route_excludes_archived_certifications_by_default(
        self, client, mock_db, monkeypatch, certifications_factory
    ):
        archived_certification_id = 101

        def fake_get_certifications(
            session,
            *,
            site_id,
            open_only,
            limit,
            offset,
            include_archived=False,
            inspector_id=None,
        ):
            assert session is mock_db
            assert include_archived is False
            assert inspector_id is None
            return [
                certifications_router.CertificationOut.model_validate(certification)
                for certification in certifications_factory(1, result="Pass")
            ]

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        response = client.get("/certifications")

        assert response.status_code == 200
        returned_ids = {certification["id"] for certification in response.json()}
        assert 100 in returned_ids
        assert archived_certification_id not in returned_ids

    def test_route_include_archived_returns_archived_certification(
        self, client, mock_db, monkeypatch, certifications_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_certification_id = 101

        def fake_get_certifications(
            session,
            *,
            site_id,
            open_only,
            limit,
            offset,
            include_archived=False,
            inspector_id=None,
        ):
            assert session is mock_db
            assert include_archived is True
            assert inspector_id is None
            return [
                certifications_router.CertificationOut.model_validate(certification)
                for certification in certifications_factory(1, result="Pass")
            ] + [
                certifications_router.CertificationOut.model_validate(
                    certifications_factory(
                        1,
                        id=archived_certification_id,
                        result="Pass",
                        archived_at=archived_at,
                        archive_reason="superseded",
                    )[0]
                )
            ]

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        response = client.get("/certifications?include_archived=true")

        assert response.status_code == 200
        returned_ids = {certification["id"] for certification in response.json()}
        assert archived_certification_id in returned_ids

    def test_route_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/certifications?limit=0")

        assert response.status_code == 422


class TestGetCertificationsRouteUnit:

    def test_returns_certifications(self, monkeypatch, certifications_factory) -> None:
        fake_session = object()
        expected_certifications = [
            certifications_router.CertificationOut.model_validate(certification)
            for certification in certifications_factory(1, result="Pass")
        ]

        def fake_get_certifications(
            session,
            *,
            site_id,
            open_only,
            limit,
            offset,
            include_archived=False,
            inspector_id=None,
        ):
            assert session is fake_session
            assert site_id == 12
            assert open_only is True
            assert limit == 10
            assert offset == 5
            assert inspector_id is None
            return expected_certifications

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        result = certifications_router.get_certifications_route(
            fake_session,
            _authorized_user=object(),
            site_id=12,
            open_only=True,
            limit=10,
            offset=5,
            inspector_id=None,
        )

        assert result == expected_certifications

    def test_returns_404_when_site_filter_does_not_exist(self, monkeypatch) -> None:
        def fake_get_certifications(
            session,
            *,
            site_id,
            open_only,
            limit,
            offset,
            include_archived=False,
            inspector_id=None,
        ):
            assert site_id == 999
            assert inspector_id is None
            return None

        monkeypatch.setattr(
            certifications_router, "get_certifications", fake_get_certifications
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.get_certifications_route(
                object(),
                _authorized_user=object(),
                site_id=999,
                open_only=False,
                limit=None,
                offset=0,
                inspector_id=None,
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


@pytest.mark.usefixtures("admin_user_override")
class TestPostNewCertificationRouteClient:
    def test_route_returns_created_certification_json(
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
            "inspector_id": None,
            "result": "Pass",
            "inspection_date": "2026-04-01",
            "resolution_date": None,
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_409_when_certification_conflicts(
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

    def test_route_returns_422_when_certification_result_is_invalid(self, client):
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


class TestPostNewCertificationRouteUnit:

    def test_returns_created_certification(self, monkeypatch) -> None:
        fake_session = object()
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            inspector_id=9,
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
            inspector_id=9,
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
            fake_session,
            _authorized_user=object(),
            certification=certification,
        )

        assert result == certifications_router.CertificationOut.model_validate(
            created_certification
        )

    def test_returns_404_when_certifier_does_not_exist(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            inspector_id=9,
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
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

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
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

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
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Site 12 does not exist."

    def test_returns_404_when_inspector_does_not_exist(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            inspector_id=9,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationInspectorNotFoundError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Inspector 9 does not exist."

    def test_returns_422_when_inspector_is_inactive(self, monkeypatch) -> None:
        certification = certifications_router.CertificationCreate(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
            inspector_id=9,
            result="Pass",
        )

        def fake_post_new_certification(session, certification_info):
            raise certifications_router.CertificationInspectorInactiveError()

        monkeypatch.setattr(
            certifications_router,
            "post_new_certification",
            fake_post_new_certification,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

        assert exc_info.value.status_code == 422
        assert exc_info.value.detail == "Inspector 9 is inactive."

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
            certifications_router.post_new_certification_route(
                object(),
                _authorized_user=object(),
                certification=certification,
            )

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


class TestPostCertificationArchivedByIdRouteClient:
    # TestClient
    def test_route_archives_active_certification(
        self,
        client,
        mock_db,
        monkeypatch,
        certifications_factory,
        assert_archived_response,
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_certification_archived_by_id(
            session, certification_id, *, archive_request
        ):
            assert session is mock_db
            assert certification_id == 100
            assert archive_request.archive_reason == "duplicate"
            return certifications_factory(
                1,
                result="Pass",
                archived_at=archived_at,
                archive_reason="duplicate",
            )[0]

        monkeypatch.setattr(
            certifications_router,
            "post_certification_archived_by_id",
            fake_post_certification_archived_by_id,
        )

        response = client.post(
            "/certifications/100/archive", json={"archive_reason": "duplicate"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json(), "duplicate")

    def test_route_archive_already_archived_certification_returns_200(
        self,
        client,
        mock_db,
        monkeypatch,
        certifications_factory,
        assert_archived_response,
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_certification_archived_by_id(
            session, certification_id, *, archive_request
        ):
            assert session is mock_db
            assert certification_id == 100
            return certifications_factory(
                1,
                result="Pass",
                archived_at=archived_at,
                archive_reason="old reason",
            )[0]

        monkeypatch.setattr(
            certifications_router,
            "post_certification_archived_by_id",
            fake_post_certification_archived_by_id,
        )

        response = client.post(
            "/certifications/100/archive", json={"archive_reason": "old reason"}
        )

        assert response.status_code == 200
        assert_archived_response(response.json())

    def test_route_returns_404_when_certification_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_certification_archived_by_id(
            session, certification_id, *, archive_request
        ):
            assert session is mock_db
            assert certification_id == 100
            return None

        monkeypatch.setattr(
            certifications_router,
            "post_certification_archived_by_id",
            fake_post_certification_archived_by_id,
        )

        response = client.post("/certifications/100/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certification does not exist: 100."}

    def test_route_returns_422_when_certification_id_is_invalid(self, client):
        response = client.post("/certifications/not-an-id/archive")

        assert response.status_code == 422


class TestPostCertificationArchivedByIdRouteUnit:

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


class TestPostCertificationRestoredByIdRouteClient:
    # TestClient
    def test_route_restores_archived_certification(
        self,
        client,
        mock_db,
        monkeypatch,
        certifications_factory,
        assert_restored_response,
    ):
        def fake_post_certification_restored_by_id(session, certification_id):
            assert session is mock_db
            assert certification_id == 100
            return certifications_factory(
                1, result="Pass", archived_at=None, archive_reason=None
            )[0]

        monkeypatch.setattr(
            certifications_router,
            "post_certification_restored_by_id",
            fake_post_certification_restored_by_id,
        )

        response = client.post("/certifications/100/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert_restored_response(response_json)

    def test_route_restore_active_certification_returns_200(
        self,
        client,
        mock_db,
        monkeypatch,
        certifications_factory,
        assert_restored_response,
    ):
        def fake_post_certification_restored_by_id(session, certification_id):
            assert session is mock_db
            assert certification_id == 100
            return certifications_factory(
                1, result="Pass", archived_at=None, archive_reason=None
            )[0]

        monkeypatch.setattr(
            certifications_router,
            "post_certification_restored_by_id",
            fake_post_certification_restored_by_id,
        )

        response = client.post("/certifications/100/restore")

        assert response.status_code == 200
        assert_restored_response(response.json())

    def test_route_returns_404_when_certification_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_certification_restored_by_id(session, certification_id):
            assert session is mock_db
            assert certification_id == 100
            return None

        monkeypatch.setattr(
            certifications_router,
            "post_certification_restored_by_id",
            fake_post_certification_restored_by_id,
        )

        response = client.post("/certifications/100/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certification does not exist: 100."}

    def test_route_returns_422_when_certification_id_is_invalid(self, client):
        response = client.post("/certifications/not-an-id/restore")

        assert response.status_code == 422


class TestPostCertificationRestoredByIdRouteUnit:

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
