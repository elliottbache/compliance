from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    ArchiveRequest,
    RegulationCreate,
    RegulationOut,
)
from compliance.db.models import Base, Certifier, Regulation
from compliance.services.regulations import (
    RegulationConflictError,
    RegulationTitleConflictError,
    get_regulation_by_id,
    get_regulations,
    post_new_regulation,
    post_regulation_archived_by_id,
    post_regulation_restored_by_id,
)


def _regulation_create(**overrides) -> RegulationCreate:
    data = {
        "title": "Fire Safety 2026",
        "description": "Fire safety requirements for commercial sites.",
        "published_date": date(2026, 1, 15),
    }
    data.update(overrides)
    return RegulationCreate(**data)


def _integrity_error(constraint_name: str | None = None) -> IntegrityError:
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("insert failed", {}, orig)


class TestGetRegulations:
    def test_returns_regulations_from_session(self, regulation_row_factory) -> None:
        session = MagicMock()
        regulations = [
            regulation_row_factory(id=3),
            regulation_row_factory(id=4, title="Electrical Safety 2026"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = regulations

        result = get_regulations(session, certifier_id=None, limit=10, offset=5)

        assert result == [
            RegulationOut.model_validate(regulation) for regulation in regulations
        ]

    def test_orders_regulations_by_published_date_title_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_regulations(session, certifier_id=None, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert (
            "ORDER BY regulations.published_date DESC, "
            "regulations.title, regulations.id" in str(stmt)
        )

    def test_excludes_archived_regulations_by_default(
        self, sqlite_session, regulation_row_factory
    ) -> None:
        active = regulation_row_factory()
        archived = regulation_row_factory(
            id=4,
            title="Archived Regulation",
            archived_at=datetime.now(UTC),
            archive_reason="replaced",
        )
        sqlite_session.add_all([active, archived])
        sqlite_session.commit()

        regulations = get_regulations(
            sqlite_session, certifier_id=None, limit=None, offset=0
        )

        assert [regulation.id for regulation in regulations] == [3]

    def test_includes_archived_regulations_when_requested(
        self, sqlite_session, regulation_row_factory
    ) -> None:
        active = regulation_row_factory()
        archived = regulation_row_factory(
            id=4,
            title="Archived Regulation",
            archived_at=datetime.now(UTC),
            archive_reason="replaced",
        )
        sqlite_session.add_all([active, archived])
        sqlite_session.commit()

        regulations = get_regulations(
            sqlite_session,
            certifier_id=None,
            limit=None,
            offset=0,
            include_archived=True,
        )

        returned_ids = {regulation.id for regulation in regulations}
        assert returned_ids == {3, 4}

    def test_filters_by_certifier_when_certifier_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certifier)
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_regulations(session, certifier_id=7, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Certifier, 7)
        assert "certifications.certifier_id = :certifier_id_1" in str(stmt)
        assert "DISTINCT" in str(stmt)

    def test_returns_none_when_certifier_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_regulations(session, certifier_id=999, limit=None, offset=0)

        assert result is None
        session.get.assert_called_once_with(Certifier, 999)
        session.execute.assert_not_called()


class TestGetRegulationById:
    def test_gets_regulation_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_regulation = MagicMock(spec=Regulation)
        session.get.return_value = expected_regulation

        result = get_regulation_by_id(session, 3)

        session.get.assert_called_once_with(Regulation, 3)
        assert result is expected_regulation

    def test_returns_none_when_regulation_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_regulation_by_id(session, 999)

        session.get.assert_called_once_with(Regulation, 999)
        assert result is None

    def test_returns_none_when_regulation_is_archived_by_default(
        self, regulation_row_factory
    ) -> None:
        session = MagicMock()
        regulation = regulation_row_factory(archived_at=datetime(2026, 5, 7))
        session.get.return_value = regulation

        result = get_regulation_by_id(session, 3)

        assert result is None

    def test_returns_archived_regulation_when_requested(
        self, regulation_row_factory
    ) -> None:
        session = MagicMock()
        regulation = regulation_row_factory(archived_at=datetime(2026, 5, 7))
        session.get.return_value = regulation

        result = get_regulation_by_id(session, 3, include_archived=True)

        assert result is regulation


class TestPostNewRegulation:
    def test_adds_and_commits_new_regulation(self) -> None:
        session = MagicMock()
        regulation = _regulation_create()

        result = post_new_regulation(session, regulation)

        session.add.assert_called_once()
        added_regulation = session.add.call_args.args[0]

        assert result is added_regulation
        assert isinstance(added_regulation, Regulation)
        assert added_regulation.title == "Fire Safety 2026"
        assert (
            added_regulation.description
            == "Fire safety requirements for commercial sites."
        )
        assert added_regulation.published_date == date(2026, 1, 15)

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error()

        with pytest.raises(RegulationConflictError):
            post_new_regulation(session, _regulation_create())

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


class TestPostRegulationArchivedById:
    def test_archives_regulation_with_stripped_reason(
        self, regulation_row_factory
    ) -> None:
        session = MagicMock()
        regulation = regulation_row_factory()
        session.get.return_value = regulation

        result = post_regulation_archived_by_id(
            session,
            3,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is regulation
        assert regulation.archived_at is not None
        assert regulation.archived_at.tzinfo is UTC
        assert regulation.archive_reason == "duplicate"
        session.get.assert_called_once_with(Regulation, 3)
        session.commit.assert_called_once_with()

    def test_does_not_rearchive_existing_archived_regulation(
        self, regulation_row_factory
    ) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        regulation = regulation_row_factory(
            archived_at=archived_at, archive_reason="old"
        )
        session.get.return_value = regulation

        result = post_regulation_archived_by_id(
            session, 3, archive_request=ArchiveRequest(archive_reason="new")
        )

        assert result is regulation
        assert regulation.archived_at == archived_at
        assert regulation.archive_reason == "old"
        session.commit.assert_not_called()

    def test_returns_none_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_regulation_archived_by_id(
            session, 3, archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Regulation, 3)
        session.commit.assert_not_called()


class TestPostRegulationRestoredById:
    def test_restores_archived_regulation(self, regulation_row_factory) -> None:
        session = MagicMock()
        regulation = regulation_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = regulation

        result = post_regulation_restored_by_id(session, 3)

        assert result is regulation
        assert regulation.archived_at is None
        assert regulation.archive_reason is None
        session.get.assert_called_once_with(Regulation, 3)
        session.commit.assert_called_once_with()

    def test_returns_active_regulation_without_commit(
        self, regulation_row_factory
    ) -> None:
        session = MagicMock()
        regulation = regulation_row_factory(archived_at=None, archive_reason=None)
        session.get.return_value = regulation

        result = post_regulation_restored_by_id(session, 3)

        assert result is regulation
        session.commit.assert_not_called()

    def test_returns_none_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_regulation_restored_by_id(session, 3)

        assert result is None
        session.get.assert_called_once_with(Regulation, 3)
        session.commit.assert_not_called()


class TestPostNewRegulationConflicts:
    def test_raises_title_conflict_when_title_already_exists(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("uq_title")

        with pytest.raises(RegulationTitleConflictError):
            post_new_regulation(session, _regulation_create())

        session.rollback.assert_called_once_with()


class TestPostRegulationArchiveRestoreIntegration:
    def test_archive_then_restore_works(self) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            regulation = Regulation(
                id=3,
                title="Fire Safety 2026",
                description="Fire safety requirements.",
                published_date=date(2026, 1, 15),
            )
            session.add(regulation)
            session.commit()

            archived = post_regulation_archived_by_id(
                session,
                3,
                archive_request=ArchiveRequest(archive_reason=" duplicate "),
            )
            archived = post_regulation_archived_by_id(
                session,
                3,
                archive_request=ArchiveRequest(archive_reason=" second "),
            )
            assert archived is not None
            assert archived.archived_at is not None
            assert archived.archive_reason == "duplicate"

            restored = post_regulation_restored_by_id(session, 3)

            assert restored is not None
            assert restored.archived_at is None
            assert restored.archive_reason is None
