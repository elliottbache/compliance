from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from compliance.db.models import (
    Certification,
    Site,
)
from compliance.services.certifications import (
    CertificationCertifierNotFoundError,
    CertificationConflictError,
    CertificationInspectorInactiveError,
    CertificationInspectorNotFoundError,
    CertificationRegulationNotFoundError,
    CertificationSiteNotFoundError,
    get_certifications,
    post_certification_archived_by_id,
    post_certification_restored_by_id,
    post_new_certification,
)
from compliance.services.schemas import (
    ArchiveRequest,
    CertificationCreate,
    CertificationOut,
)


def _certification_create(**overrides) -> CertificationCreate:
    data = {
        "certifier_id": 7,
        "regulation_id": 3,
        "site_id": 12,
        "inspector_id": None,
        "result": "Pass",
        "inspection_date": date(2026, 4, 1),
        "resolution_date": None,
    }
    data.update(overrides)
    return CertificationCreate(**data)


class TestGetCertifications:
    def test_returns_certifications_from_session(
        self, certification_row_factory
    ) -> None:
        session = MagicMock()
        certifications = [
            certification_row_factory(),
            certification_row_factory(id=43, regulation_id=4),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = (
            certifications
        )

        result = get_certifications(
            session,
            site_id=None,
            open_only=False,
            limit=10,
            offset=5,
            inspector_id=None,
        )

        assert result == [
            CertificationOut.model_validate(certification)
            for certification in certifications
        ]

    def test_orders_certifications_by_regulation_inspection_date_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifications(
            session,
            site_id=None,
            open_only=False,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        stmt = session.execute.call_args.args[0]
        assert (
            "ORDER BY certifications.regulation_id, "
            "certifications.inspection_date DESC, certifications.id" in str(stmt)
        )

    def test_filters_by_site_when_site_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Site)
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_certifications(
            session,
            site_id=12,
            open_only=False,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Site, 12)
        assert "certifications.site_id = :site_id_1" in str(stmt)

    def test_returns_none_when_site_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certifications(
            session,
            site_id=999,
            open_only=False,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        assert result is None
        session.get.assert_called_once_with(Site, 999)
        session.execute.assert_not_called()

    def test_filters_open_certifications_by_resolution_date(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifications(
            session,
            site_id=None,
            open_only=True,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        stmt = session.execute.call_args.args[0]
        assert "certifications.resolution_date IS NULL" in str(stmt)

    def test_excludes_archived_certifications_by_default(
        self, sqlite_session, db_factory, certification_row_factory, archived_fields
    ) -> None:
        db_factory()
        archived = certification_row_factory(
            id=43,
            **archived_fields("superseded"),
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        certifications = get_certifications(
            sqlite_session,
            site_id=None,
            open_only=False,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        assert [certification.id for certification in certifications] == [42]

    def test_excludes_certifications_for_archived_client_by_default(
        self, sqlite_session, db_factory, archived_fields
    ) -> None:
        db_factory(
            client_overrides=archived_fields("closed"),
        )

        certifications = get_certifications(
            sqlite_session,
            site_id=None,
            open_only=False,
            limit=None,
            offset=0,
            inspector_id=None,
        )

        assert certifications == []

    def test_includes_archived_certifications_when_requested(
        self, sqlite_session, db_factory, certification_row_factory, archived_fields
    ) -> None:
        db_factory()
        archived = certification_row_factory(
            id=43,
            **archived_fields("superseded"),
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        certifications = get_certifications(
            sqlite_session,
            site_id=None,
            open_only=False,
            limit=None,
            offset=0,
            include_archived=True,
            inspector_id=None,
        )

        returned_ids = {certification.id for certification in certifications}
        assert returned_ids == {42, 43}


class TestPostNewCertification:
    def test_adds_and_commits_new_certification(self) -> None:
        session = MagicMock()
        certification = _certification_create()

        result = post_new_certification(session, certification)

        session.add.assert_called_once()
        added_certification = session.add.call_args.args[0]

        assert result is added_certification
        assert isinstance(added_certification, Certification)
        assert added_certification.certifier_id == 7
        assert added_certification.regulation_id == 3
        assert added_certification.site_id == 12
        assert added_certification.inspector_id is None
        assert added_certification.result == "Pass"
        assert added_certification.inspection_date == date(2026, 4, 1)
        assert added_certification.resolution_date is None

    def test_sets_optional_inspector_id_when_provided(self) -> None:
        session = MagicMock()
        certification = _certification_create(inspector_id=9)

        result = post_new_certification(session, certification)

        added_certification = session.add.call_args.args[0]
        assert result is added_certification
        assert added_certification.inspector_id == 9

    def test_skips_inspector_lookup_when_inspector_id_is_none(self) -> None:
        session = MagicMock()
        certification = _certification_create(inspector_id=None)

        post_new_certification(session, certification)

        session.get.assert_not_called()
        session.add.assert_called_once()
        session.commit.assert_called_once_with()

    def test_raises_inspector_not_found_when_inspector_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None
        certification = _certification_create(inspector_id=9)

        with pytest.raises(CertificationInspectorNotFoundError):
            post_new_certification(session, certification)

        session.get.assert_called_once()
        session.add.assert_not_called()
        session.commit.assert_not_called()

    def test_raises_inactive_inspector_error_when_inspector_is_inactive(self) -> None:
        session = MagicMock()
        session.get.return_value = SimpleNamespace(id=9, is_active=False)
        certification = _certification_create(inspector_id=9)

        with pytest.raises(CertificationInspectorInactiveError):
            post_new_certification(session, certification)

        session.get.assert_called_once()
        session.add.assert_not_called()
        session.commit.assert_not_called()

    def test_allows_certification_under_archived_site(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            site_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )
        certification = _certification_create(
            certifier_id=7,
            regulation_id=3,
            site_id=12,
        )

        result = post_new_certification(sqlite_session, certification)

        assert result.id is not None
        assert result.site_id == 12

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory()
        certification = _certification_create()

        with pytest.raises(CertificationConflictError):
            post_new_certification(session, certification)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_certifier_error_when_certifier_does_not_exist(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory(
            "fk_certifications_certifier_id_certifiers"
        )

        with pytest.raises(CertificationCertifierNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()

    def test_raises_regulation_error_when_regulation_does_not_exist(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory(
            "fk_certifications_regulation_id_regulations"
        )

        with pytest.raises(CertificationRegulationNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()

    def test_raises_site_error_when_site_does_not_exist(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory(
            "fk_certifications_site_id_sites"
        )

        with pytest.raises(CertificationSiteNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()


class TestPostCertificationArchivedById:
    def test_archives_certification_with_stripped_reason(
        self, certification_row_factory, assert_archived_record
    ) -> None:
        session = MagicMock()
        certification = certification_row_factory()
        session.get.return_value = certification

        result = post_certification_archived_by_id(
            session,
            42,
            archive_request=ArchiveRequest(archive_reason="  duplicate  "),
        )

        assert result is certification
        assert_archived_record(certification, "duplicate")
        session.get.assert_called_once_with(Certification, 42)
        session.commit.assert_called_once_with()

    def test_does_not_rearchive_existing_archived_certification(
        self, certification_row_factory
    ) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)
        session = MagicMock()
        certification = certification_row_factory(
            archived_at=archived_at, archive_reason="old"
        )
        session.get.return_value = certification

        result = post_certification_archived_by_id(
            session, 42, archive_request=ArchiveRequest(archive_reason="new")
        )

        assert result is certification
        assert certification.archived_at == archived_at
        assert certification.archive_reason == "old"
        session.commit.assert_not_called()

    def test_returns_none_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_certification_archived_by_id(
            session, 42, archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Certification, 42)
        session.commit.assert_not_called()


class TestPostCertificationRestoredById:
    def test_restores_archived_certification(
        self, certification_row_factory, assert_restored_record
    ) -> None:
        session = MagicMock()
        certification = certification_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = certification

        result = post_certification_restored_by_id(session, 42)

        assert result is certification
        assert_restored_record(certification)
        session.get.assert_called_once_with(Certification, 42)
        session.commit.assert_called_once_with()

    def test_returns_active_certification_without_commit(
        self, certification_row_factory
    ) -> None:
        session = MagicMock()
        certification = certification_row_factory(archived_at=None, archive_reason=None)
        session.get.return_value = certification

        result = post_certification_restored_by_id(session, 42)

        assert result is certification
        session.commit.assert_not_called()

    def test_returns_none_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_certification_restored_by_id(session, 42)

        assert result is None
        session.get.assert_called_once_with(Certification, 42)
        session.commit.assert_not_called()


class TestPostCertificationArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, sqlite_session, db_factory, assert_archive_restore_round_trip
    ) -> None:
        db_factory()

        assert_archive_restore_round_trip(
            sqlite_session,
            42,
            archive_fn=post_certification_archived_by_id,
            restore_fn=post_certification_restored_by_id,
        )
