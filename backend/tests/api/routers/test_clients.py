from datetime import UTC, datetime

import pytest
from compliance.api.routers import clients as clients_router
from fastapi import HTTPException


@pytest.mark.usefixtures("viewer_user_override")
class TestGetClientsRouteClient:
    # TestClient
    def test_route_returns_client_json(
        self, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_get_clients(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert limit == 2
            assert offset == 1
            assert include_archived is False
            return [
                client_record_factory(),
                client_record_factory(
                    nif="B1234567C",
                    company_name="Beta Corp",
                    contact_name="Jane Doe",
                    email="jane.doe@beta.com",
                    telephone=5550456,
                ),
            ]

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        response = client.get("/clients?limit=2&offset=1")

        assert response.status_code == 200
        assert response.json() == [
            {
                "nif": "A1234567B",
                "company_name": "Acme Corp",
                "contact_name": "John Doe",
                "email": "john.doe@acme.com",
                "telephone": 5550123,
                "archived_at": None,
                "archive_reason": None,
            },
            {
                "nif": "B1234567C",
                "company_name": "Beta Corp",
                "contact_name": "Jane Doe",
                "email": "jane.doe@beta.com",
                "telephone": 5550456,
                "archived_at": None,
                "archive_reason": None,
            },
        ]

    def test_route_passes_include_archived_to_service(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_clients(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert limit is None
            assert offset == 0
            assert include_archived is True
            return []

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        response = client.get("/clients?include_archived=true")

        assert response.status_code == 200
        assert response.json() == []

    def test_route_excludes_archived_clients_by_default(
        self, client, mock_db, monkeypatch, client_record_factory
    ):
        archived_client_nif = "B1234567C"

        def fake_get_clients(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is False
            return [client_record_factory()]

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        response = client.get("/clients")

        assert response.status_code == 200
        returned_nifs = {client_record["nif"] for client_record in response.json()}
        assert "A1234567B" in returned_nifs
        assert archived_client_nif not in returned_nifs

    def test_route_include_archived_returns_archived_client(
        self, client, mock_db, monkeypatch, client_record_factory
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        archived_client_nif = "B1234567C"

        def fake_get_clients(session, *, limit, offset, include_archived=False):
            assert session is mock_db
            assert include_archived is True
            return [
                client_record_factory(),
                client_record_factory(
                    nif=archived_client_nif,
                    company_name="Archived Corp",
                    archived_at=archived_at,
                    archive_reason="merged",
                ),
            ]

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        response = client.get("/clients?include_archived=true")

        assert response.status_code == 200
        response_json = response.json()
        returned_nifs = {client_record["nif"] for client_record in response_json}
        assert archived_client_nif in returned_nifs

    def test_route_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/clients?limit=0")

        assert response.status_code == 422


class TestGetClientsRouteUnit:
    def test_returns_clients(self, monkeypatch, client_record_factory) -> None:
        fake_session = object()
        clients = [client_record_factory()]
        expected_clients = [
            clients_router.ClientOut.model_validate(client) for client in clients
        ]

        def fake_get_clients(session, *, limit, offset, include_archived=False):
            assert session is fake_session
            assert limit == 10
            assert offset == 5
            assert include_archived is False
            return clients

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        result = clients_router.get_clients_route(
            fake_session,
            _authorized_user=object(),
            limit=10,
            offset=5,
        )

        assert result == expected_clients

    def test_registers_client_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[clients_router.ClientOut]


@pytest.mark.usefixtures("admin_user_override")
class TestPostNewClientRouteClient:
    # TestClient
    def test_route_returns_client_json_when_found(
        self, main_module, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_post_new_client(session, client_record):
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
            "archived_at": None,
            "archive_reason": None,
        }

    def test_route_returns_409_when_client_already_exists(
        self, main_module, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_post_new_client(session, client_record):
            assert session is mock_db
            raise clients_router.ClientConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        response = client.post("/clients", json=vars(client_record_factory()))

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Client was not added because of a data conflict."
        }

    def test_route_returns_422_when_client_is_invalid(
        self, client, client_record_factory
    ):
        response = client.post("/clients", json=vars(client_record_factory(nif=12)))

        assert response.status_code == 422


class TestPostNewClientRouteUnit:
    def test_returns_created_client(self, main_module, monkeypatch) -> None:
        fake_session = object()
        client = clients_router.ClientCreate(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )
        expected_client = clients_router.ClientOut(
            **client.model_dump(), archived_at=None, archive_reason=None
        )

        def fake_post_new_client(session, client_info):
            assert client_info is client
            assert session is fake_session
            return expected_client

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        result = clients_router.post_new_client_route(
            fake_session,
            _authorized_user=object(),
            client=client,
        )

        assert result == expected_client

    def test_returns_409_when_client_is_not_created(
        self, main_module, monkeypatch
    ) -> None:
        client = clients_router.ClientCreate(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(session, client_info):
            raise clients_router.ClientConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(
                object(),
                _authorized_user=object(),
                client=client,
            )

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail == "Client was not added because of a data conflict."
        )

    def test_returns_409_when_client_nif_already_exists(
        self, main_module, monkeypatch
    ) -> None:
        client = clients_router.ClientCreate(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(session, client_info):
            raise clients_router.ClientNifConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(
                object(),
                _authorized_user=object(),
                client=client,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Client with NIF A1234567B already exists."

    def test_returns_409_when_client_company_name_already_exists(
        self, main_module, monkeypatch
    ) -> None:
        client = clients_router.ClientCreate(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        def fake_post_new_client(session, client_info):
            raise clients_router.ClientCompanyNameConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(
                object(),
                _authorized_user=object(),
                client=client,
            )

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail
            == "Client with company name Acme Compliance already exists."
        )

    def test_registers_client_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is clients_router.ClientOut
        assert route.status_code == 201


class TestPostClientArchivedByNifRouteClient:
    # TestClient
    def test_route_archives_active_client(
        self,
        client,
        mock_db,
        monkeypatch,
        client_record_factory,
        assert_archived_response,
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            assert session is mock_db
            assert nif == "A1234567B"
            assert archive_request.archive_reason == "duplicate client"
            return client_record_factory(
                archived_at=archived_at, archive_reason="duplicate client"
            )

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        response = client.post(
            "/clients/A1234567B/archive",
            json={"archive_reason": "duplicate client"},
        )

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["nif"] == "A1234567B"
        assert_archived_response(response_json, "duplicate client")

    def test_route_returns_already_archived_client(
        self,
        client,
        mock_db,
        monkeypatch,
        client_record_factory,
        assert_archived_response,
    ):
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            assert session is mock_db
            assert nif == "A1234567B"
            return client_record_factory(
                archived_at=archived_at, archive_reason="old reason"
            )

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        response = client.post("/clients/A1234567B/archive")

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["nif"] == "A1234567B"
        assert_archived_response(response_json, "old reason")

    def test_route_returns_404_when_client_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            assert session is mock_db
            assert nif == "A1234567B"
            return None

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        response = client.post("/clients/A1234567B/archive")

        assert response.status_code == 404
        assert response.json() == {"detail": "Client does not exist: A1234567B."}

    def test_route_returns_422_when_nif_is_invalid(self, client):
        response = client.post("/clients/invalid/archive")

        assert response.status_code == 422


class TestPostClientArchivedByNifRouteUnit:

    def test_returns_archived_client(self, monkeypatch, client_record_factory) -> None:
        fake_session = object()
        archive_request = clients_router.ArchiveRequest(
            archive_reason="duplicate client"
        )
        expected_client = clients_router.ClientOut.model_validate(
            client_record_factory(archive_reason="duplicate client")
        )

        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            assert session is fake_session
            assert nif == "A1234567B"
            assert archive_request.archive_reason == "duplicate client"
            return expected_client

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        result = clients_router.post_client_archived_by_nif_route(
            fake_session, "A1234567B", archive_request
        )

        assert result == expected_client

    def test_defaults_missing_archive_request(self, monkeypatch) -> None:
        fake_session = object()
        expected_client = clients_router.ClientOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            assert session is fake_session
            assert nif == "A1234567B"
            assert archive_request == clients_router.ArchiveRequest()
            return expected_client

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        result = clients_router.post_client_archived_by_nif_route(
            fake_session, "A1234567B"
        )

        assert result == expected_client

    def test_returns_404_when_client_does_not_exist(self, monkeypatch) -> None:
        def fake_post_client_archived_by_nif(session, nif, *, archive_request):
            return None

        monkeypatch.setattr(
            clients_router,
            "post_client_archived_by_nif",
            fake_post_client_archived_by_nif,
        )

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_client_archived_by_nif_route(object(), "A1234567B")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Client does not exist: A1234567B."


class TestPostClientRestoredByNifRouteClient:
    # TestClient
    def test_route_restores_archived_client(
        self,
        client,
        mock_db,
        monkeypatch,
        client_record_factory,
        assert_restored_response,
    ):
        def fake_post_client_restored_by_nif(session, nif):
            assert session is mock_db
            assert nif == "A1234567B"
            return client_record_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            clients_router,
            "post_client_restored_by_nif",
            fake_post_client_restored_by_nif,
        )

        response = client.post("/clients/A1234567B/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["nif"] == "A1234567B"
        assert_restored_response(response_json)

    def test_route_returns_active_client(
        self,
        client,
        mock_db,
        monkeypatch,
        client_record_factory,
        assert_restored_response,
    ):
        def fake_post_client_restored_by_nif(session, nif):
            assert session is mock_db
            assert nif == "A1234567B"
            return client_record_factory(archived_at=None, archive_reason=None)

        monkeypatch.setattr(
            clients_router,
            "post_client_restored_by_nif",
            fake_post_client_restored_by_nif,
        )

        response = client.post("/clients/A1234567B/restore")

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["nif"] == "A1234567B"
        assert_restored_response(response_json)

    def test_route_returns_404_when_client_does_not_exist(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_client_restored_by_nif(session, nif):
            assert session is mock_db
            assert nif == "A1234567B"
            return None

        monkeypatch.setattr(
            clients_router,
            "post_client_restored_by_nif",
            fake_post_client_restored_by_nif,
        )

        response = client.post("/clients/A1234567B/restore")

        assert response.status_code == 404
        assert response.json() == {"detail": "Client does not exist: A1234567B."}

    def test_route_returns_422_when_nif_is_invalid(self, client):
        response = client.post("/clients/invalid/restore")

        assert response.status_code == 422


class TestPostClientRestoredByNifRouteUnit:

    def test_returns_restored_client(self, monkeypatch) -> None:
        fake_session = object()
        expected_client = clients_router.ClientOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
            archived_at=None,
            archive_reason=None,
        )

        def fake_post_client_restored_by_nif(session, nif):
            assert session is fake_session
            assert nif == "A1234567B"
            return expected_client

        monkeypatch.setattr(
            clients_router,
            "post_client_restored_by_nif",
            fake_post_client_restored_by_nif,
        )

        result = clients_router.post_client_restored_by_nif_route(
            fake_session, "A1234567B"
        )

        assert result == expected_client

    def test_returns_404_when_client_does_not_exist(self, monkeypatch) -> None:
        def fake_post_client_restored_by_nif(session, nif):
            return None

        monkeypatch.setattr(
            clients_router,
            "post_client_restored_by_nif",
            fake_post_client_restored_by_nif,
        )

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_client_restored_by_nif_route(object(), "A1234567B")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Client does not exist: A1234567B."
