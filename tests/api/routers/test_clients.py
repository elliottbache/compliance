import pytest
from fastapi import HTTPException

from compliance.api.routers import clients as clients_router


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
