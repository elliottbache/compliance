import pytest
from fastapi import HTTPException

from compliance.api.routers import certifiers as certifiers_router


class TestGetCertifiersRoute:
    # TestClient
    def test_client_returns_certifier_json(
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
            },
            {
                "organization_name": "VoltGuard",
                "id": 11,
            },
        ]

    def test_client_returns_422_when_limit_is_invalid(self, client):
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
    def test_client_returns_certifier_json_when_found(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_get_certifier_by_id(certifier_id, session, *, include_archived=False):
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
        }

    def test_client_returns_404_when_certifier_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_certifier_by_id(certifier_id, session, *, include_archived=False):
            assert certifier_id == 10
            assert session is mock_db
            return None

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        response = client.get("/certifiers/10")

        assert response.status_code == 404
        assert response.json() == {"detail": "Certifier 10 not found."}

    def test_client_returns_422_when_certifier_id_is_invalid(self, client):
        response = client.get("/certifiers/not-an-id")

        assert response.status_code == 422

    # unittests
    def test_returns_certifier_when_found(
        self, monkeypatch, certifier_record_factory
    ) -> None:
        fake_session = object()
        certifier = certifier_record_factory()
        expected_certifier = certifiers_router.CertifierOut.model_validate(certifier)

        def fake_get_certifier_by_id(certifier_id, session, *, include_archived=False):
            assert certifier_id == 10
            assert session is fake_session
            return certifier

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        result = certifiers_router.get_certifiers_by_id_route(10, fake_session)

        assert result == expected_certifier

    def test_returns_404_when_certifier_is_not_found(self, monkeypatch) -> None:
        def fake_get_certifier_by_id(certifier_id, session, *, include_archived=False):
            return None

        monkeypatch.setattr(
            certifiers_router, "get_certifier_by_id", fake_get_certifier_by_id
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.get_certifiers_by_id_route(10, object())

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
    def test_client_returns_certifier_json_when_created(
        self, client, mock_db, monkeypatch, certifier_record_factory
    ):
        def fake_post_new_certifier(certifier_record, session):
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
        }

    def test_client_returns_409_when_certifier_already_exists(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_certifier(certifier_record, session):
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

    def test_client_returns_422_when_certifier_is_invalid(self, client):
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
        )

        def fake_post_new_certifier(certifier_info, session):
            assert certifier_info is certifier
            assert session is fake_session
            return expected_certifier

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        result = certifiers_router.post_new_certifier_route(certifier, fake_session)

        assert result == expected_certifier

    def test_returns_409_when_certifier_is_not_created(self, monkeypatch) -> None:
        certifier = certifiers_router.CertifierCreate(
            organization_name="SafeCheck Inc."
        )

        def fake_post_new_certifier(certifier_info, session):
            raise certifiers_router.CertifierConflictError

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_new_certifier_route(certifier, object())

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

        def fake_post_new_certifier(certifier_info, session):
            raise certifiers_router.CertifierOrganizationNameConflictError

        monkeypatch.setattr(
            certifiers_router, "post_new_certifier", fake_post_new_certifier
        )

        with pytest.raises(HTTPException) as exc_info:
            certifiers_router.post_new_certifier_route(certifier, object())

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
