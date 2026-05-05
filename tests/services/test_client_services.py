from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    ClientInOut,
)
from compliance.db.models import Client
from compliance.services.clients import (
    ClientCompanyNameConflictError,
    ClientConflictError,
    ClientNifConflictError,
    get_client_by_nif,
    get_clients,
    post_new_client,
)


def _client(**overrides) -> Client:
    client = Client(
        nif="A1234567B",
        company_name="Acme Compliance",
        contact_name="Ada Lovelace",
        email="ada@example.com",
        telephone=123456789,
    )
    for key, value in overrides.items():
        setattr(client, key, value)
    return client


class TestGetClients:
    def test_returns_clients_from_session(self) -> None:
        session = MagicMock()
        clients = [
            _client(nif="A1234567B", company_name="Acme Compliance"),
            _client(nif="B1234567C", company_name="Beta Compliance"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = clients

        result = get_clients(session, limit=10, offset=5)

        assert result == [ClientInOut.model_validate(client) for client in clients]

    def test_orders_clients_by_company_name_then_nif(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_clients(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY clients.company_name, clients.nif" in str(stmt)


class TestGetClientByNif:
    def test_returns_client_when_found(self) -> None:
        session = MagicMock()
        client = _client()
        session.get.return_value = client

        result = get_client_by_nif("A1234567B", session)

        assert result == ClientInOut.model_validate(client)
        session.get.assert_called_once_with(Client, "A1234567B")

    def test_returns_none_when_client_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_client_by_nif("A1234567B", session)

        assert result is None
        session.get.assert_called_once_with(Client, "A1234567B")


class TestPostNewClient:
    def test_adds_and_commits_new_client(self) -> None:
        session = MagicMock()
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        post_new_client(client, session)

        session.add.assert_called_once()
        added_client = session.add.call_args.args[0]

        assert isinstance(added_client, Client)
        assert added_client.nif == "A1234567B"
        assert added_client.company_name == "Acme Compliance"
        assert added_client.contact_name == "Ada Lovelace"
        assert added_client.email == "ada@example.com"
        assert added_client.telephone == 123456789

    def test_rolls_back_and_raises_nif_conflict_when_nif_already_exists(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )
        monkeypatch.setattr(
            "compliance.services.clients.get_constraint_name",
            lambda exc: "pk_clients",
        )

        with pytest.raises(ClientNifConflictError):
            post_new_client(client, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_rolls_back_and_raises_company_name_conflict_when_company_name_exists(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )
        monkeypatch.setattr(
            "compliance.services.clients.get_constraint_name",
            lambda exc: "uq_clients_company_name",
        )

        with pytest.raises(ClientCompanyNameConflictError):
            post_new_client(client, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_rolls_back_and_raises_generic_conflict_for_unknown_integrity_error(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )
        monkeypatch.setattr(
            "compliance.services.clients.get_constraint_name",
            lambda exc: "unexpected_constraint",
        )

        with pytest.raises(ClientConflictError):
            post_new_client(client, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()
