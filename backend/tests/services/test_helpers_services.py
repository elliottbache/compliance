from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from compliance.api.schemas import ArchiveRequest, AttachmentWithContextOut
from compliance.schemas import FindingHistory
from compliance.services._helpers import (
    _build_finding_history_from_site_attachments,
    archive_record_by_id,
    format_attachment,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from sqlalchemy.exc import IntegrityError


class TestFormatAttachment:
    def test_formats_attachment_without_finding_links(
        self, attachment_row_factory, certification_row_factory, regulation_row_factory
    ) -> None:
        attachment = attachment_row_factory()
        certification = certification_row_factory()
        regulation = regulation_row_factory(id=300)

        rows = [
            {
                "Attachment": attachment,
                "Certification": certification,
                "Regulation": regulation,
                "Finding": None,
                "Rule": None,
            }
        ]

        result = format_attachment(rows)

        assert result == AttachmentWithContextOut(
            id=50,
            file_name="evidence.pdf",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
            certification_id=42,
            inspection_date=date(2026, 4, 1),
            regulation_id=3,
            regulation_title="Fire Safety 2026",
            finding_links=[],
        )

    def test_collects_finding_links(
        self,
        attachment_row_factory,
        certification_row_factory,
        regulation_row_factory,
        finding_row_factory,
        rule_row_factory,
    ) -> None:
        attachment = attachment_row_factory()
        certification = certification_row_factory()
        regulation = regulation_row_factory()

        rows = [
            {
                "Attachment": attachment,
                "Certification": certification,
                "Regulation": regulation,
                "Finding": finding_row_factory(id=1, finding="Missing document"),
                "Rule": rule_row_factory(
                    rule_index="7 CFR 205.201",
                    title="Organic plan",
                    description="Plan must be complete.",
                ),
            },
            {
                "Attachment": attachment,
                "Certification": certification,
                "Regulation": regulation,
                "Finding": finding_row_factory(id=2, finding="Incomplete record"),
                "Rule": rule_row_factory(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            },
        ]

        result = format_attachment(rows)

        assert [link.finding_id for link in result.finding_links] == [1, 2]
        assert [link.rule_index for link in result.finding_links] == [
            "7 CFR 205.201",
            "7 CFR 205.202",
        ]


class TestGetConstraintName:
    def test_returns_constraint_name_from_integrity_error_diag(self) -> None:
        orig = SimpleNamespace(
            diag=SimpleNamespace(constraint_name="uq_sites_nif_city")
        )
        error = IntegrityError("statement", "params", orig)

        assert get_constraint_name(error) == "uq_sites_nif_city"

    def test_returns_none_when_diag_is_missing(self) -> None:
        error = IntegrityError("statement", "params", SimpleNamespace())

        assert get_constraint_name(error) is None


class TestRecordIsVisible:
    def test_returns_false_when_record_is_none(self) -> None:
        assert record_is_visible(None, include_archived=False) is False

    def test_returns_true_for_active_record(self) -> None:
        record = SimpleNamespace(archived_at=None)

        assert record_is_visible(record, include_archived=False) is True

    def test_returns_false_for_archived_record_by_default(self) -> None:
        record = SimpleNamespace(archived_at=datetime.now(UTC))

        assert record_is_visible(record, include_archived=False) is False

    def test_returns_true_for_archived_record_when_requested(self) -> None:
        record = SimpleNamespace(archived_at=datetime.now(UTC))

        assert record_is_visible(record, include_archived=True) is True

    def test_treats_mock_archived_at_as_visible(self) -> None:
        record = SimpleNamespace(archived_at=Mock())

        assert record_is_visible(record, include_archived=False) is True


class TestArchiveRecordById:
    def test_archives_record_and_strips_archive_reason(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = record

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            71,
            ArchiveRequest(archive_reason=" duplicate site "),
        )

        assert result is record
        assert record.archived_at is not None
        assert record.archived_at.tzinfo is UTC
        assert record.archive_reason == "duplicate site"
        session.get.assert_called_once_with(SimpleNamespace, 71)
        session.commit.assert_called_once_with()

    def test_archives_record_with_empty_archive_reason_as_none(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = record

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            71,
            ArchiveRequest(archive_reason=""),
        )

        assert result is record
        assert record.archived_at is not None
        assert record.archive_reason is None
        session.commit.assert_called_once_with()

    def test_archives_record_with_omitted_archive_reason_as_none(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = record

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            71,
            ArchiveRequest(),
        )

        assert result is record
        assert record.archived_at is not None
        assert record.archive_reason is None
        session.commit.assert_called_once_with()

    def test_archives_record_with_whitespace_only_archive_reason_as_none(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = record

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            71,
            ArchiveRequest(archive_reason="   "),
        )

        assert result is record
        assert record.archived_at is not None
        assert record.archive_reason is None
        session.commit.assert_called_once_with()

    def test_returns_none_when_record_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            999,
            ArchiveRequest(archive_reason="missing"),
        )

        assert result is None
        session.get.assert_called_once_with(SimpleNamespace, 999)
        session.commit.assert_not_called()

    def test_returns_already_archived_record_unchanged(self) -> None:
        archived_at = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
        session = MagicMock()
        record = SimpleNamespace(
            archived_at=archived_at,
            archive_reason="existing reason",
        )
        session.get.return_value = record

        result = archive_record_by_id(
            session,
            SimpleNamespace,
            71,
            ArchiveRequest(archive_reason="new reason"),
        )

        assert result is record
        assert record.archived_at == archived_at
        assert record.archive_reason == "existing reason"
        session.commit.assert_not_called()


class TestRestoreRecordById:
    def test_restores_archived_record(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(
            archived_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            archive_reason="closed",
        )
        session.get.return_value = record

        result = restore_record_by_id(session, SimpleNamespace, 71)

        assert result is record
        assert record.archived_at is None
        assert record.archive_reason is None
        session.get.assert_called_once_with(SimpleNamespace, 71)
        session.commit.assert_called_once_with()

    def test_returns_active_record_unchanged(self) -> None:
        session = MagicMock()
        record = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = record

        result = restore_record_by_id(session, SimpleNamespace, 71)

        assert result is record
        assert record.archived_at is None
        assert record.archive_reason is None
        session.commit.assert_not_called()

    def test_returns_none_when_record_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = restore_record_by_id(session, SimpleNamespace, 999)

        assert result is None
        session.get.assert_called_once_with(SimpleNamespace, 999)
        session.commit.assert_not_called()


class TestBuildFindingHistoryFromSiteAttachments:
    def test_builds_finding_history_from_row(self) -> None:
        row = {
            "Finding": SimpleNamespace(id=1, finding="Missing document"),
            "Rule": SimpleNamespace(
                rule_index="7 CFR 205.201",
                title="Organic plan",
                description="Plan must be complete.",
            ),
        }

        result = _build_finding_history_from_site_attachments(row)

        assert result == FindingHistory(
            finding_id=1,
            finding="Missing document",
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Plan must be complete.",
        )

    def test_raises_key_error_when_required_fields_are_missing(self) -> None:
        row = {
            "Finding": SimpleNamespace(id=1),
            "Rule": SimpleNamespace(rule_index="7 CFR 205.201"),
        }

        with pytest.raises(
            KeyError,
            match="Missing finding history fields in site attachment row",
        ):
            _build_finding_history_from_site_attachments(row)
