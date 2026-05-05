import pytest
from fastapi import HTTPException

from compliance.api.routers import clients as clients_router


class TestGetClientsRoute:
    # TestClient
    def test_client_returns_client_json(
        self, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_get_clients(session, limit, offset):
            assert session is mock_db
            assert limit == 2
            assert offset == 1
            return [
                clients_router.ClientInOut.model_validate(client_record_factory()),
                clients_router.ClientInOut.model_validate(
                    client_record_factory(
                        nif="B1234567C",
                        company_name="Beta Corp",
                        contact_name="Jane Doe",
                        email="jane.doe@beta.com",
                        telephone=5550456,
                    )
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
            },
            {
                "nif": "B1234567C",
                "company_name": "Beta Corp",
                "contact_name": "Jane Doe",
                "email": "jane.doe@beta.com",
                "telephone": 5550456,
            },
        ]

    def test_client_returns_422_when_limit_is_invalid(self, client):
        response = client.get("/clients?limit=0")

        assert response.status_code == 422

    # unittests
    def test_returns_clients(self, monkeypatch, client_record_factory) -> None:
        fake_session = object()
        expected_clients = [
            clients_router.ClientInOut.model_validate(client_record_factory())
        ]

        def fake_get_clients(session, limit, offset):
            assert session is fake_session
            assert limit == 10
            assert offset == 5
            return expected_clients

        monkeypatch.setattr(clients_router, "get_clients", fake_get_clients)

        result = clients_router.get_clients_route(fake_session, limit=10, offset=5)

        assert result == expected_clients

    def test_registers_client_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[clients_router.ClientInOut]


class TestGetClientByNifRoute:
    # TestClient
    def test_client_returns_client_json_when_found(
        self, client, mock_db, monkeypatch, client_record_factory
    ):
        def fake_get_client_by_nif(nif, session):
            assert nif == "A1234567B"
            assert session is mock_db
            return clients_router.ClientInOut.model_validate(client_record_factory())

        monkeypatch.setattr(clients_router, "get_client_by_nif", fake_get_client_by_nif)

        response = client.get("/clients/A1234567B")

        assert response.status_code == 200
        assert response.json() == {
            "nif": "A1234567B",
            "company_name": "Acme Corp",
            "contact_name": "John Doe",
            "email": "john.doe@acme.com",
            "telephone": 5550123,
        }

    def test_client_returns_404_when_client_is_not_found(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_client_by_nif(nif, session):
            assert nif == "A1234567B"
            assert session is mock_db
            return None

        monkeypatch.setattr(clients_router, "get_client_by_nif", fake_get_client_by_nif)

        response = client.get("/clients/A1234567B")

        assert response.status_code == 404
        assert response.json() == {"detail": "Client A1234567B not found."}

    def test_client_returns_422_when_nif_is_invalid(self, client):
        response = client.get("/clients/short")

        assert response.status_code == 422

    # unittests
    def test_returns_client_when_found(
        self, monkeypatch, client_record_factory
    ) -> None:
        fake_session = object()
        expected_client = clients_router.ClientInOut.model_validate(
            client_record_factory()
        )

        def fake_get_client_by_nif(nif, session):
            assert nif == "A1234567B"
            assert session is fake_session
            return expected_client

        monkeypatch.setattr(clients_router, "get_client_by_nif", fake_get_client_by_nif)

        result = clients_router.get_clients_by_nif_route("A1234567B", fake_session)

        assert result == expected_client

    def test_returns_404_when_client_is_not_found(self, monkeypatch) -> None:
        def fake_get_client_by_nif(nif, session):
            return None

        monkeypatch.setattr(clients_router, "get_client_by_nif", fake_get_client_by_nif)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.get_clients_by_nif_route("A1234567B", object())

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Client A1234567B not found."

    def test_registers_client_detail_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/clients/{nif}"
        )

        assert route.response_model is clients_router.ClientInOut


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
        def fake_post_new_client(client_record, session):
            assert session is mock_db
            raise clients_router.ClientConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        response = client.post("/clients", json=vars(client_record_factory()))

        assert response.status_code == 409
        assert response.json() == {
            "detail": "Client was not added because of a data conflict."
        }

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
            raise clients_router.ClientConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(client, object())

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail == "Client was not added because of a data conflict."
        )

    def test_returns_409_when_client_nif_already_exists(
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
            raise clients_router.ClientNifConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(client, object())

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "Client with NIF A1234567B already exists."

    def test_returns_409_when_client_company_name_already_exists(
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
            raise clients_router.ClientCompanyNameConflictError

        monkeypatch.setattr(clients_router, "post_new_client", fake_post_new_client)

        with pytest.raises(HTTPException) as exc_info:
            clients_router.post_new_client_route(client, object())

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

        assert route.response_model is clients_router.ClientInOut
        assert route.status_code == 201
