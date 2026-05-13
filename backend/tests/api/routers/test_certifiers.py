from datetime import UTC, datetime

import pytest
from compliance.api.routers import certifiers as certifiers_router
from fastapi import HTTPException


class TestGetCertifiersRoute:
    # TestClient
    def test_route_returns_certifier_json(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_get_certifiers(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert limit == 2
            assert offset == 1
            return [
                certifier_record_factory(),
                certifier_record_factory(
                    id=11,
                    organization_name="VoltGuard",
                ),
            ]

        monkeypatch.setattr(certifiers_router, "get_certifiers", fake_get_certifiers)

        response = client.get("/certifiers?limit=2&offset=1")

        assert response.status_code == 200
        assert response.json() == [
            {
                "organization_name": "SafeCheck Inc.",
                "id": 10,
                "archived_at": None,
                "archive_reason": None,
            },
            {
                "organization_name": "VoltGuard",
                "id": 11,
                "archived_at": None,
                "archive_reason": None,
            },
        ]

    def test_route_excludes_archived_certifiers_by_default(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        archived_certifier_id = 11

        def fake_get_certifiers(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is False
            return [certifier_record_factory()]

        monkeypatch.setattr(certifiers_router, "get_certifiers", fake_get_certifiers)

        response = client.get("/certifiers")

        assert response.status_code == 200
        returned_ids = {certifier["id"] for certifier in response.json()}
        assert 10 in returned_ids
        assert archived_certifier_id not in returned_ids

    def test_route_include_archived_returns_archived_certifier(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_certifier_id = 11

        def fake_get_certifiers(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is True
            return [
                certifier_record_factory(),
                certifier_record_factory(
                    id=archived_certifier_id,
                    organization_name="Archived Certifier",
                    archived_at=archived_at,
                    archive_reason="merged",
                ),
            ]

        monkeypatch.setattr(certifiers_router, "get_certifiers", fake_get_certifiers)

        response = client.get("/certifiers?include_archived=true")

        assert response.status_code == 200
        returned_ids = {certifier["id"] for certifier in response.json()}
        assert archived_certifier_id in returned_ids

    def test_route_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/certifiers?limit=0")

        assert response.status_code == 422

    # unittests
    def test_returns_certifiers(self, monkeypatch, certifier_record_factory) -> None:
        fake_session = object()
        certifiers = [certifier_record_factory()]
        expected_certifiers = [
            certifiers_router.CertifierOut.model_validate(certifier)
            for certifier in certifiers
        ]

        def fake_get_certifiers(session, *, limit, offset, include_archived=False):
            assert session is fake_session
            assert limit == 10
            assert offset == 5
            return certifiers

        monkeypatch.setattr(certifiers_router, "get_certifiers", fake_get_certifiers)

        result = certifiers_router.get_certifiers_route(
            fake_session, limit=10, offset=5
        )

        assert result == expected_certifiers

    def test_registers_certifier_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifiers"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[certifiers_router.CertifierOut]


class TestGetCertifierByIdRoute:
    # TestClient
    def test_route_returns_certifier_json_when_found(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_get_certifier_by_id(session, certifier_id, *, include_archived=False):
            assert certifier_id == 10
            assert session is mock_db
            return certifier_record_factory()

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        response = client.get("/certifiers/10")

        assert response.status_code == 200
        assert response.json() == {
            "organization_name": "SafeCheck Inc.",
            "id": 10,
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_404_when_certifier_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_certifier_by_id(session, certifier_id, *, include_archived=False):
            assert certifier_id == 10
            assert session is mock_db
            return None

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        response = client.get("/certifiers/10")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certifier 10 not found."}

    def test_route_returns_422_when_certifier_id_is_invalid(self, client):
        response = client.get("/certifiers/not-an-id")

        assert response.status_code == 422

    # unittests
    def test_returns_certifier_when_found(
        self, monkeypatch, certifier_record_factory
    ) -> None:
        fake_session = object()
        certifier = certifier_record_factory()
        expected_certifier = certifiers_router.CertifierOut.model_validate(certifier)

        def fake_get_certifier_by_id(session, certifier_id, *, include_archived=False):
            assert certifier_id == 10
            assert session is fake_session
            return certifier

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        result = certifiers_router.get_certifiers_by_id_route(fake_session, 10)

        assert result == expected_certifier

    def test_returns_404_when_certifier_is_not_found(self, monkeypatch) -> None:
        def fake_get_certifier_by_id(session, certifier_id, *, include_archived=False):
            return None

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.get_certifiers_by_id_route(object(), 10)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certifier 10 not found."

    def test_registers_certifier_detail_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifiers/{certifier_id}"
        )

        assert route.response_model is certifiers_router.CertifierOut


class TestPostNewCertifierRoute:
    # TestClient
    def test_route_returns_certifier_json_when_created(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_post_new_certifier(session, certifier_record):
            assert certifier_record.organization_name == "SafeCheck Inc."
            assert session is mock_db
            return certifier_record_factory()

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        response = client.post(
            "/certifiers",
            json={"organization_name": "SafeCheck Inc."},
        )

        assert response.status_code == 201
        assert response.json() == {
            "organization_name": "SafeCheck Inc.",
            "id": 10,
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_409_when_certifier_already_exists(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_certifier(session, certifier_record):
            assert session is mock_db
            raise certifiers_router.CertifierConflictError

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        response = client.post(
            "/certifiers",
            json={"organization_name": "SafeCheck Inc."},
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Certifier was not added because of a data conflict."
        }

    def test_route_returns_422_when_certifier_is_invalid(self, client):
        response = client.post("/certifiers", json={"organization_name": ""})

        assert response.status_code == 422

    # unittests
    def test_returns_created_certifier(self, monkeypatch) -> None:
        fake_session = object()
        certifier = certifiers_router.CertifierCreate(
            organization_name="SafeCheck Inc."
        )
        expected_certifier = certifiers_router.CertifierOut(
            id=10,
            organization_name="SafeCheck Inc.",
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_new_certifier(session, certifier_info):
            assert certifier_info is certifier
            assert session is fake_session
            return expected_certifier

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        result = certifiers_router.post_new_certifier_route(fake_session, certifier)

        assert result == expected_certifier

    def test_returns_409_when_certifier_is_not_created(self, monkeypatch) -> None:
        certifier = certifiers_router.CertifierCreate(
            organization_name="SafeCheck Inc."
        )

        def fake_post_new_certifier(session, certifier_info):
            raise certifiers_router.CertifierConflictError

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_new_certifier_route(object(), certifier)

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail
            == "Certifier was not added because of a data conflict."
        )

    def test_returns_409_when_certifier_organization_name_already_exists(
        self, monkeypatch
    ) -> None:
        certifier = certifiers_router.CertifierCreate(
            organization_name="SafeCheck Inc."
        )

        def fake_post_new_certifier(session, certifier_info):
            raise certifiers_router.CertifierOrganizationNameConflictError

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_new_certifier_route(object(), certifier)

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail
            == "Certifier with organization name SafeCheck Inc. already exists."
        )

    def test_registers_certifier_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/certifiers"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is certifiers_router.CertifierOut
        assert route.status_code == 201


class TestPostCertifierArchivedByIdRoute:
    # TestClient
    def test_route_archives_active_certifier(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_certifier_archived_by_id(
            session, certifier_id, *, archive_request
        ):
            assert session is mock_db
            assert certifier_id == 10
            assert archive_request.archive_reason == "duplicate"
            return certifier_record_factory(
                archived_at=archived_at, archive_reason="duplicate"
            )

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_archived_by_id",
            fake_post_certifier_archived_by_id,
        )

        response = client.post(
            "/certifiers/10/archive", json={"archive_reason": "duplicate"}
        )

        assert response.status_code == 200
        assert response.json()["archived_at"] is not None
        assert response.json()["archive_reason"] == "duplicate"

    def test_route_archive_already_archived_certifier_returns_200(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_certifier_archived_by_id(
            session, certifier_id, *, archive_request
        ):
            assert session is mock_db
            assert certifier_id == 10
            return certifier_record_factory(
                archived_at=archived_at, archive_reason="old reason"
            )

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_archived_by_id",
            fake_post_certifier_archived_by_id,
        )

        response = client.post(
            "/certifiers/10/archive", json={"archive_reason": "old reason"}
        )

        assert response.status_code == 200
        assert response.json()["archived_at"] is not None

    def test_route_returns_404_when_certifier_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_certifier_archived_by_id(
            session, certifier_id, *, archive_request
        ):
            assert session is mock_db
            assert certifier_id == 10
            return None

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_archived_by_id",
            fake_post_certifier_archived_by_id,
        )

        response = client.post("/certifiers/10/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certifier does not exist: 10."}

    def test_route_returns_422_when_certifier_id_is_invalid(self, client):
        response = client.post("/certifiers/not-an-id/archive")

        assert response.status_code == 422

    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected = certifiers_router.CertifierOut(
            id=10,
            organization_name="SafeCheck Inc.",
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_certifier_archived_by_id(
            session, certifier_id, *, archive_request
        ):
            assert session is fake_session
            assert certifier_id == 10
            assert archive_request == certifiers_router.ArchiveRequest()
            return expected

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_archived_by_id",
            fake_post_certifier_archived_by_id,
        )

        result = certifiers_router.post_certifier_archived_by_id_route(fake_session, 10)

        assert result == expected

    def test_returns_404_when_certifier_does_not_exist(self, monkeypatch) -> None:
        def fake_post_certifier_archived_by_id(
            session, certifier_id, *, archive_request
        ):
            return None

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_archived_by_id",
            fake_post_certifier_archived_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_certifier_archived_by_id_route(object(), 10)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certifier does not exist: 10."


class TestPostCertifierRestoredByIdRoute:
    # TestClient
    def test_route_restores_archived_certifier(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_post_certifier_restored_by_id(session, certifier_id):
            assert session is mock_db
            assert certifier_id == 10
            return certifier_record_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_restored_by_id",
            fake_post_certifier_restored_by_id,
        )

        response = client.post("/certifiers/10/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["archived_at"] is None
        assert response_json["archive_reason"] is None

    def test_route_restore_active_certifier_returns_200(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_post_certifier_restored_by_id(session, certifier_id):
            assert session is mock_db
            assert certifier_id == 10
            return certifier_record_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_restored_by_id",
            fake_post_certifier_restored_by_id,
        )

        response = client.post("/certifiers/10/restore")

        assert response.status_code == 200
        assert response.json()["archived_at"] is None

    def test_route_returns_404_when_certifier_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_certifier_restored_by_id(session, certifier_id):
            assert session is mock_db
            assert certifier_id == 10
            return None

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_restored_by_id",
            fake_post_certifier_restored_by_id,
        )

        response = client.post("/certifiers/10/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certifier does not exist: 10."}

    def test_route_returns_422_when_certifier_id_is_invalid(self, client):
        response = client.post("/certifiers/not-an-id/restore")

        assert response.status_code == 422

    def test_returns_restored_certifier(self, monkeypatch) -> None:
        fake_session = object()
        expected = certifiers_router.CertifierOut(
            id=10,
            organization_name="SafeCheck Inc.",
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_certifier_restored_by_id(session, certifier_id):
            assert session is fake_session
            assert certifier_id == 10
            return expected

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_restored_by_id",
            fake_post_certifier_restored_by_id,
        )

        result = certifiers_router.post_certifier_restored_by_id_route(fake_session, 10)

        assert result == expected

    def test_returns_404_when_certifier_does_not_exist(self, monkeypatch) -> None:
        def fake_post_certifier_restored_by_id(session, certifier_id):
            return None

        monkeypatch.setattr(
            certifiers_router,
            "post_certifier_restored_by_id",
            fake_post_certifier_restored_by_id,
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_certifier_restored_by_id_route(object(), 10)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Certifier does not exist: 10."
