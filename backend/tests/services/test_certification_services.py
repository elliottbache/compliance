from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    ArchiveRequest,
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
)
from compliance.db.models import (
    Certification,
    Certifier,
    Client,
    Regulation,
    Site,
)
from compliance.services.certifications import (
    CertificationCertifierNotFoundError,
    CertificationConflictError,
    CertificationRegulationNotFoundError,
    CertificationSiteNotFoundError,
    _format_certification_attachments,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications,
    post_certification_archived_by_id,
    post_certification_restored_by_id,
    post_new_certification,
)


def _certification_create(**overrides) -> CertificationCreate:
    data = {
        "certifier_id": 7,
        "regulation_id": 3,
        "site_id": 12,
        "result": "Pass",
        "inspection_date": date(2026, 4, 1),
        "resolution_date": None,
    }
    data.update(overrides)
    return CertificationCreate(**data)


def _integrity_error(constraint_name: str | None = None) -> IntegrityError:
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("insert failed", {}, orig)


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
            session, site_id=None, open_only=False, limit=10, offset=5
        )

        assert result == [
            CertificationOut.model_validate(certification)
            for certification in certifications
        ]

    def test_orders_certifications_by_regulation_inspection_date_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifications(session, site_id=None, open_only=False, limit=None, offset=0)

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
            session, site_id=12, open_only=False, limit=None, offset=0
        )

        stmt = session.execute.call_args.args[0]
        assert result == []
        session.get.assert_called_once_with(Site, 12)
        assert "certifications.site_id = :site_id_1" in str(stmt)

    def test_returns_none_when_site_filter_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certifications(
            session, site_id=999, open_only=False, limit=None, offset=0
        )

        assert result is None
        session.get.assert_called_once_with(Site, 999)
        session.execute.assert_not_called()

    def test_filters_open_certifications_by_resolution_date(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_certifications(session, site_id=None, open_only=True, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "certifications.resolution_date IS NULL" in str(stmt)

    def test_excludes_archived_certifications_by_default(
        self, sqlite_session, db_factory, certification_row_factory
    ) -> None:
        db_factory()
        archived = certification_row_factory(
            id=43,
            archived_at=datetime.now(UTC),
            archive_reason="superseded",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        certifications = get_certifications(
            sqlite_session, site_id=None, open_only=False, limit=None, offset=0
        )

        assert [certification.id for certification in certifications] == [42]

    def test_includes_archived_certifications_when_requested(
        self, sqlite_session, db_factory, certification_row_factory
    ) -> None:
        db_factory()
        archived = certification_row_factory(
            id=43,
            archived_at=datetime.now(UTC),
            archive_reason="superseded",
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
        )

        returned_ids = {certification.id for certification in certifications}
        assert returned_ids == {42, 43}


class TestGetCertificationById:
    def test_gets_certification_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_certification = MagicMock(spec=Certification)
        session.execute.return_value.scalar_one_or_none.return_value = (
            expected_certification
        )

        result = get_certification_by_id(session, 42)

        stmt = session.execute.call_args.args[0]
        assert "JOIN sites" in str(stmt)
        assert "JOIN regulations" in str(stmt)
        assert "JOIN certifiers" in str(stmt)
        assert "certifications.id = :id_1" in str(stmt)
        assert result is expected_certification

    def test_returns_none_when_certification_is_not_found(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        result = get_certification_by_id(session, 999)

        session.execute.assert_called_once()
        assert result is None

    def test_includes_archived_certification_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certification_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_certification_by_id(sqlite_session, 42)

        assert result is not None
        assert result.archive_reason == "closed"

    def test_returns_none_when_archived_certification_excluded(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        result = get_certification_by_id(session, 42, include_archived=False)

        stmt = session.execute.call_args.args[0]
        print(f"stmt: {stmt}")
        print(f"result: {result}")
        assert "certifications.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)
        assert "regulations.archived_at IS NULL" in str(stmt)
        assert "certifiers.archived_at IS NULL" in str(stmt)
        assert result is None


class TestGetCertificationAttachmentsById:
    def test_returns_none_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certification_attachments_by_id(session, 100)

        session.get.assert_called_once_with(Certification, 100)
        session.execute.assert_not_called()
        assert result is None

    def test_returns_none_when_certification_is_archived_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certification_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "superseded",
            },
        )

        result = get_certification_attachments_by_id(sqlite_session, 42)

        assert result is None

    def test_returns_empty_attachment_list_when_certification_has_no_attachments(
        self,
    ) -> None:
        session = MagicMock()

        certification = SimpleNamespace(
            archived_at=None,
            site_id=12,
            certifier_id=7,
            regulation_id=3,
        )
        site = SimpleNamespace(archived_at=None, nif="A1234567B")
        client = SimpleNamespace(archived_at=None)
        certifier = SimpleNamespace(archived_at=None)
        regulation = SimpleNamespace(archived_at=None)

        session.get.side_effect = [
            certification,
            site,
            client,
            certifier,
            regulation,
        ]
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_certification_attachments_by_id(session, 100)

        session.execute.assert_called_once()
        assert session.get.call_args_list == [
            call(Certification, 100),
            call(Site, 12),
            call(Client, "A1234567B"),
            call(Certifier, 7),
            call(Regulation, 3),
        ]
        assert result == CertificationAttachmentsOut(
            certification_id=100,
            attachments=[],
        )

    def test_omits_archived_attachments_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "duplicate",
            },
        )

        result = get_certification_attachments_by_id(sqlite_session, 42)

        assert result == CertificationAttachmentsOut(
            certification_id=42, attachments=[]
        )

    def test_formats_certification_attachments_when_query_returns_rows(
        self, attachment_out_factory
    ) -> None:
        rows = [attachment_out_factory()]
        session = MagicMock()

        certification = SimpleNamespace(
            archived_at=None,
            site_id=12,
            certifier_id=7,
            regulation_id=3,
        )
        site = SimpleNamespace(archived_at=None, nif="A1234567B")
        client = SimpleNamespace(archived_at=None)
        certifier = SimpleNamespace(archived_at=None)
        regulation = SimpleNamespace(archived_at=None)

        session.get.side_effect = [
            certification,
            site,
            client,
            certifier,
            regulation,
        ]
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_certification_attachments_by_id(session, 100)

        session.execute.assert_called_once()
        assert result == _format_certification_attachments(rows)

    def test_orders_attachments_by_attachment_id_then_finding_id(self) -> None:
        session = MagicMock()

        certification = SimpleNamespace(
            archived_at=None,
            site_id=12,
            certifier_id=7,
            regulation_id=3,
        )
        site = SimpleNamespace(archived_at=None, nif="A1234567B")
        client = SimpleNamespace(archived_at=None)
        certifier = SimpleNamespace(archived_at=None)
        regulation = SimpleNamespace(archived_at=None)

        session.get.side_effect = [
            certification,
            site,
            client,
            certifier,
            regulation,
        ]
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_certification_attachments_by_id(session, 100)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY attachments.id, findings.id" in str(stmt)

    def test_excludes_archived_attachments_by_default(self) -> None:
        session = MagicMock()

        certification = SimpleNamespace(
            archived_at=None,
            site_id=12,
            certifier_id=7,
            regulation_id=3,
        )
        site = SimpleNamespace(archived_at=None, nif="A1234567B")
        client = SimpleNamespace(archived_at=None)
        certifier = SimpleNamespace(archived_at=None)
        regulation = SimpleNamespace(archived_at=None)

        session.get.side_effect = [
            certification,
            site,
            client,
            certifier,
            regulation,
        ]
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_certification_attachments_by_id(session, 100)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)
        assert "certifiers.archived_at IS NULL" in str(stmt)
        assert "findings.archived_at IS NULL" in str(stmt)
        assert "rules.archived_at IS NULL" in str(stmt)
        assert "AND (findings.id IS NULL" not in str(stmt)
        assert "AND (rules.id IS NULL" not in str(stmt)

    def test_includes_archived_attachments_when_requested(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certification)
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_certification_attachments_by_id(session, 100, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" not in str(stmt)
        assert "sites.archived_at IS NULL" not in str(stmt)
        assert "certifiers.archived_at IS NULL" not in str(stmt)
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "rules.archived_at IS NULL" not in str(stmt)


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
        assert added_certification.result == "Pass"
        assert added_certification.inspection_date == date(2026, 4, 1)
        assert added_certification.resolution_date is None

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error()
        certification = _certification_create()

        with pytest.raises(CertificationConflictError):
            post_new_certification(session, certification)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_certifier_error_when_certifier_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error(
            "certifications_certifier_id_fkey"
        )

        with pytest.raises(CertificationCertifierNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()

    def test_raises_regulation_error_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error(
            "certifications_regulation_id_fkey"
        )

        with pytest.raises(CertificationRegulationNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()

    def test_raises_site_error_when_site_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("certifications_site_id_fkey")

        with pytest.raises(CertificationSiteNotFoundError):
            post_new_certification(session, _certification_create())

        session.rollback.assert_called_once_with()


class TestFormatCertificationAttachmentsOut:
    def test_creates_certification_attachments_with_finding_link(
        self, attachment_out_factory
    ) -> None:
        result = _format_certification_attachments([attachment_out_factory()])

        assert result.certification_id == 100
        assert len(result.attachments) == 1
        assert result.attachments[0].id == 50
        assert result.attachments[0].regulation_title == "USDA Organic"
        assert len(result.attachments[0].finding_links) == 1
        assert result.attachments[0].finding_links[0].finding_id == 1

    def test_groups_multiple_findings_under_same_attachment(
        self, attachment_out_factory
    ) -> None:
        rows = [
            attachment_out_factory(),
            attachment_out_factory(
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_certification_attachments(rows)

        assert len(result.attachments) == 1
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_groups_attachments_by_id_without_reordering(
        self, attachment_out_factory
    ) -> None:
        second_attachment = SimpleNamespace(
            id=60,
            file_type="pdf",
            file_path="dummy/second.pdf",
            description="Second attachment",
            uploaded_at=datetime(2026, 4, 4, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
            certification_id=42,
        )
        rows = [
            attachment_out_factory(Attachment=second_attachment),
            attachment_out_factory(),
            attachment_out_factory(
                Attachment=second_attachment,
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_certification_attachments(rows)

        assert [attachment.id for attachment in result.attachments] == [60, 50]
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_raises_stop_iteration_when_rows_are_empty(self) -> None:
        with pytest.raises(StopIteration):
            _format_certification_attachments([])

    def test_raises_value_error_when_first_row_is_empty(self) -> None:
        with pytest.raises(ValueError, match="First attachment row is empty"):
            _format_certification_attachments([{}])


class TestPostCertificationArchivedById:
    def test_archives_certification_with_stripped_reason(
        self, certification_row_factory
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
        assert certification.archived_at is not None
        assert certification.archived_at.tzinfo is UTC
        assert certification.archive_reason == "duplicate"
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
    def test_restores_archived_certification(self, certification_row_factory) -> None:
        session = MagicMock()
        certification = certification_row_factory(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old",
        )
        session.get.return_value = certification

        result = post_certification_restored_by_id(session, 42)

        assert result is certification
        assert certification.archived_at is None
        assert certification.archive_reason is None
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
    def test_archive_then_restore_works(self, sqlite_session, db_factory) -> None:
        db_factory()

        archived = post_certification_archived_by_id(
            sqlite_session,
            42,
            archive_request=ArchiveRequest(archive_reason=" duplicate "),
        )
        archived = post_certification_archived_by_id(
            sqlite_session,
            42,
            archive_request=ArchiveRequest(archive_reason=" second "),
        )

        assert archived is not None
        assert archived.archived_at is not None
        assert archived.archive_reason == "duplicate"

        restored = post_certification_restored_by_id(sqlite_session, 42)

        assert restored is not None
        assert restored.archived_at is None
        assert restored.archive_reason is None
