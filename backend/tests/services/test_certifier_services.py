from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    ArchiveRequest,
    CertifierCreate,
)
from compliance.db.models import Certifier
from compliance.services.certifiers import (
    CertifierConflictError,
    CertifierOrganizationNameConflictError,
    get_certifier_by_id,
    get_certifiers,
    post_certifier_archived_by_id,
    post_certifier_restored_by_id,
    post_new_certifier,
)


def _certifier(**overrides) -> Certifier:
    certifier = Certifier(
        id=10,
        organization_name="SafeCheck Inc.",
    )
    for key, value in overrides.items():
        setattr(certifier, key, value)
    return certifier


class TestGetCertifiers:
    def test_returns_certifiers_from_session(self) -> None:
        session = MagicMock()
        certifiers = [
            _certifier(id=10, organization_name="SafeCheck Inc."),
            _certifier(id=11, organization_name="VoltGuard"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = certifiers

        result = get_certifiers(session, limit=10, offset=5)

        assert result == certifiers

    def test_orders_certifiers_by_organization_name_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifiers(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY certifiers.organization_name, certifiers.id" in str(stmt)

    def test_excludes_archived_certifiers_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certifier_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        certifiers = get_certifiers(sqlite_session, limit=None, offset=0)

        assert [certifier.id for certifier in certifiers] == []

    def test_includes_archived_certifiers_when_requested(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory()

        archived = _certifier(
            id=11,
            organization_name="Archived Certifier",
            archived_at=datetime.now(UTC),
            archive_reason="merged",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        certifiers = get_certifiers(
            sqlite_session, limit=None, offset=0, include_archived=True
        )

        returned_ids = {certifier.id for certifier in certifiers}
        assert returned_ids == {7, 11}


class TestGetCertifierById:
    def test_returns_certifier_when_found(self) -> None:
        session = MagicMock()
        certifier = _certifier()
        session.get.return_value = certifier

        result = get_certifier_by_id(session, 10)

        assert result is certifier
        session.get.assert_called_once_with(Certifier, 10)

    def test_returns_none_when_certifier_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certifier_by_id(session, 10)

        assert result is None
        session.get.assert_called_once_with(Certifier, 10)

    def test_include_archived_certifier_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certifier_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_certifier_by_id(sqlite_session, 7)

        assert result is not None
        assert result.archive_reason == "closed"

    def test_returns_none_when_archived_certifier_excluded(self) -> None:
        session = MagicMock()
        certifier = _certifier(archived_at=datetime(2026, 5, 7))
        session.get.return_value = certifier

        result = get_certifier_by_id(session, 10, include_archived=False)

        assert result is None


class TestPostNewCertifier:
    def test_adds_and_commits_new_certifier(self) -> None:
        session = MagicMock()
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")

        post_new_certifier(session, certifier)

        session.add.assert_called_once()
        added_certifier = session.add.call_args.args[0]

        assert isinstance(added_certifier, Certifier)
        assert added_certifier.organization_name == "SafeCheck Inc."

    def test_rolls_back_and_raises_organization_name_conflict_when_name_exists(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")
        monkeypatch.setattr(
            "compliance.services.certifiers.get_constraint_name",
            lambda exc: "uq_organization_name",
        )

        with pytest.raises(CertifierOrganizationNameConflictError):
            post_new_certifier(session, certifier)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


class TestPostCertifierArchivedById:
    def test_archives_certifier_with_stripped_reason(self) -> None:
        session = MagicMock()
        certifier = _certifier()
        session.get.return_value = certifier

        result = post_certifier_archived_by_id(
            session,
            10,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is certifier
        assert certifier.archived_at is not None
        assert certifier.archived_at.tzinfo is UTC
        assert certifier.archive_reason == "duplicate"
        session.get.assert_called_once_with(Certifier, 10)
        session.commit.assert_called_once_with()

    def test_does_not_rearchive_existing_archived_certifier(self) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        certifier = _certifier(archived_at=archived_at, archive_reason="old")
        session.get.return_value = certifier

        result = post_certifier_archived_by_id(
            session, 10, archive_request=ArchiveRequest(archive_reason="new")
        )

        assert result is certifier
        assert certifier.archived_at == archived_at
        assert certifier.archive_reason == "old"
        session.commit.assert_not_called()

    def test_returns_none_when_certifier_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_certifier_archived_by_id(
            session, 10, archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Certifier, 10)
        session.commit.assert_not_called()


class TestPostCertifierRestoredById:
    def test_restores_archived_certifier(self) -> None:
        session = MagicMock()
        certifier = _certifier(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = certifier

        result = post_certifier_restored_by_id(session, 10)

        assert result is certifier
        assert certifier.archived_at is None
        assert certifier.archive_reason is None
        session.get.assert_called_once_with(Certifier, 10)
        session.commit.assert_called_once_with()

    def test_returns_active_certifier_without_commit(self) -> None:
        session = MagicMock()
        certifier = _certifier(archived_at=None, archive_reason=None)
        session.get.return_value = certifier

        result = post_certifier_restored_by_id(session, 10)

        assert result is certifier
        session.commit.assert_not_called()

    def test_returns_none_when_certifier_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_certifier_restored_by_id(session, 10)

        assert result is None
        session.get.assert_called_once_with(Certifier, 10)
        session.commit.assert_not_called()

    def test_rolls_back_and_raises_generic_conflict_for_unknown_integrity_error(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        certifier = CertifierCreate(organization_name="SafeCheck Inc.")
        monkeypatch.setattr(
            "compliance.services.certifiers.get_constraint_name",
            lambda exc: "unexpected_constraint",
        )

        with pytest.raises(CertifierConflictError):
            post_new_certifier(session, certifier)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


class TestPostCertifierArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory()

        archived = post_certifier_archived_by_id(
            sqlite_session,
            7,
            archive_request=ArchiveRequest(archive_reason=" duplicate "),
        )
        archived = post_certifier_archived_by_id(
            sqlite_session,
            7,
            archive_request=ArchiveRequest(archive_reason=" second "),
        )

        assert archived is not None
        assert archived.archived_at is not None
        assert archived.archive_reason == "duplicate"

        restored = post_certifier_restored_by_id(sqlite_session, 7)

        assert restored is not None
        assert restored.archived_at is None
        assert restored.archive_reason is None
