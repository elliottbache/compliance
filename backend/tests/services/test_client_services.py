from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import Client
from compliance.services.clients import (
    ClientCompanyNameConflictError,
    ClientConflictError,
    ClientNifConflictError,
    get_clients,
    post_client_archived_by_nif,
    post_client_restored_by_nif,
    post_new_client,
)
from compliance.services.schemas import (
    ArchiveRequest,
    ClientCreate,
)
from sqlalchemy.exc import IntegrityError


class TestGetClients:
    def test_returns_clients_from_session(self, client_row_factory) -> None:
        session = MagicMock()
        clients = [
            client_row_factory(nif="A1234567B", company_name="Acme Compliance"),
            client_row_factory(nif="B1234567C", company_name="Beta Compliance"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = clients

        result = get_clients(session, limit=10, offset=5)

        assert result == clients

    def test_orders_clients_by_company_name_then_nif(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_clients(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY clients.company_name, clients.nif" in str(stmt)

    def test_excludes_archived_clients_by_default(
        self, sqlite_session, db_factory, client_row_factory, archived_fields
    ) -> None:
        db_factory()
        archived = client_row_factory(
            nif="B1234567C",
            company_name="Archived Co",
            contact_name="Grace",
            email=None,
            telephone=None,
            **archived_fields("merged"),
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        clients = get_clients(sqlite_session, limit=None, offset=0)

        assert [client.nif for client in clients] == ["A1234567B"]

    def test_includes_archived_clients_when_requested(
        self, sqlite_session, db_factory, client_row_factory, archived_fields
    ) -> None:
        db_factory()
        archived = client_row_factory(
            nif="B1234567C",
            company_name="Archived Co",
            contact_name="Grace",
            email=None,
            telephone=None,
            **archived_fields("merged"),
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        clients = get_clients(
            sqlite_session,
            limit=None,
            offset=0,
            include_archived=True,
        )

        returned_nifs = {client.nif for client in clients}
        assert returned_nifs == {"A1234567B", "B1234567C"}


class TestPostNewClient:
    def test_adds_and_commits_new_client(self) -> None:
        session = MagicMock()
        client = ClientCreate(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        post_new_client(session, client)

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
        client = ClientCreate(
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
            post_new_client(session, client)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_rolls_back_and_raises_company_name_conflict_when_company_name_exists(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientCreate(
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
            post_new_client(session, client)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


class TestPostClientArchivedByNif:
    def test_archives_client_with_stripped_reason(
        self, client_row_factory, assert_archived_record
    ) -> None:
        session = MagicMock()
        client = client_row_factory()
        session.get.return_value = client

        result = post_client_archived_by_nif(
            session,
            "A1234567B",
            archive_request=ArchiveRequest(archive_reason="  duplicate client  "),
        )

        assert result is client
        assert_archived_record(client, "duplicate client")
        session.get.assert_called_once_with(Client, "A1234567B")
        session.commit.assert_called_once_with()

    def test_stores_none_when_reason_is_blank(self, client_row_factory) -> None:
        session = MagicMock()
        client = client_row_factory()
        session.get.return_value = client

        post_client_archived_by_nif(
            session,
            "A1234567B",
            archive_request=ArchiveRequest(archive_reason="   "),
        )

        assert client.archive_reason is None
        session.commit.assert_called_once_with()

    def test_returns_existing_archived_client_without_commit(
        self, client_row_factory
    ) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        client = client_row_factory(
            archived_at=archived_at, archive_reason="old reason"
        )
        session.get.return_value = client

        result = post_client_archived_by_nif(
            session,
            "A1234567B",
            archive_request=ArchiveRequest(archive_reason="new reason"),
        )

        assert result is client
        assert client.archived_at == archived_at
        assert client.archive_reason == "old reason"
        session.commit.assert_not_called()

    def test_returns_none_when_client_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_client_archived_by_nif(
            session, "A1234567B", archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Client, "A1234567B")
        session.commit.assert_not_called()


class TestPostClientRestoredByNif:
    def test_restores_archived_client(
        self, client_row_factory, assert_restored_record
    ) -> None:
        session = MagicMock()
        client = client_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="duplicate client",
        )
        session.get.return_value = client

        result = post_client_restored_by_nif(session, "A1234567B")

        assert result is client
        assert_restored_record(client)
        session.get.assert_called_once_with(Client, "A1234567B")
        session.commit.assert_called_once_with()

    def test_returns_active_client_without_commit(self, client_row_factory) -> None:
        session = MagicMock()
        client = client_row_factory(archived_at=None, archive_reason=None)
        session.get.return_value = client

        result = post_client_restored_by_nif(session, "A1234567B")

        assert result is client
        session.commit.assert_not_called()

    def test_returns_none_when_client_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_client_restored_by_nif(session, "A1234567B")

        assert result is None
        session.get.assert_called_once_with(Client, "A1234567B")
        session.commit.assert_not_called()

    def test_rolls_back_and_raises_generic_conflict_for_unknown_integrity_error(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientCreate(
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
            post_new_client(session, client)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


class TestClientArchiveRestoreService:
    def test_archive_then_restore_works(
        self, sqlite_session, db_factory, assert_archive_restore_round_trip
    ) -> None:
        db_factory()

        assert_archive_restore_round_trip(
            sqlite_session,
            "A1234567B",
            archive_fn=post_client_archived_by_nif,
            restore_fn=post_client_restored_by_nif,
        )
