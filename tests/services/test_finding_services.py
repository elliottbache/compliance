from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.api.schemas import ArchiveRequest, FindingAttachmentOut, FindingOut
from compliance.db.models import (
    Attachment,
    Certification,
    Certifier,
    Client,
    Finding,
    Regulation,
    Rule,
    Site,
)
from compliance.services.findings import (
    _build_finding_out,
    _format_findings,
    get_finding_by_id,
    get_findings,
    post_finding_archived_by_id,
    post_finding_restored_by_id,
)


def finding_row(**overrides):
    row = {
        "Finding": SimpleNamespace(
            id=1,
            finding="Missing document",
            archived_at=None,
            archive_reason=None,
        ),
        "Certification": SimpleNamespace(
            id=100,
            site_id=71,
            resolution_date=date(2026, 4, 15),
        ),
        "Regulation": SimpleNamespace(
            title="USDA Organic",
        ),
        "Rule": SimpleNamespace(
            id=5,
            rule_index="7 CFR 205.201",
            title="Organic plan",
            description="Producer must maintain an organic system plan.",
        ),
        "Attachment": None,
    }
    row.update(overrides)
    return row


class TestGetFindings:
    def test_outer_joins_attachment_details(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_findings(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
        )

        stmt = session.execute.call_args.args[0]

        assert "LEFT OUTER JOIN finding_attachments" in str(stmt)
        assert "LEFT OUTER JOIN attachments" in str(stmt)

    def test_excludes_archived_findings_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        findings = get_findings(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
        )

        assert [finding.finding_id for finding in findings] == [1]

    def test_includes_archived_findings_when_requested(
        self, monkeypatch, sqlite_session, db_factory, finding_row_factory
    ) -> None:
        db_factory()

        archived = finding_row_factory(
            id=2,
            archived_at=datetime.now(UTC),
            archive_reason="resolved",
        )
        sqlite_session.add(archived)
        sqlite_session.commit()

        monkeypatch.setattr(
            "compliance.services.findings._format_findings",
            lambda rows: [row["Finding"].id for row in rows],
        )
        findings = get_findings(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
            include_archived=True,
        )

        assert findings == [1, 2]

    def test_filters_by_attachment_id_when_attachment_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Attachment)
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_findings(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=50,
            open_only=False,
        )

        stmt = session.execute.call_args.args[0]

        session.get.assert_called_once_with(Attachment, 50)
        assert "finding_attachments.attachment_id = :attachment_id_1" in str(stmt)

    def test_checks_filter_parent_records_before_querying(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(archived_at=None),  # Site for site_id=71
            SimpleNamespace(  # Certification for certification_id=100
                archived_at=None,
                site_id=71,
                certifier_id=7,
                regulation_id=5,
            ),
            SimpleNamespace(archived_at=None, nif="A1234567B"),  # parent Site
            SimpleNamespace(archived_at=None),  # parent Client
            SimpleNamespace(archived_at=None),  # parent Certifier
            SimpleNamespace(archived_at=None),  # parent Regulation
            SimpleNamespace(archived_at=None),  # Rule
            SimpleNamespace(archived_at=None),  # Attachment
        ]
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_findings(
            session,
            site_id=71,
            certification_id=100,
            rule_id=5,
            attachment_id=50,
            open_only=True,
        )

        assert session.get.call_args_list == [
            ((Site, 71),),
            ((Certification, 100),),
            ((Site, 71),),
            ((Client, "A1234567B"),),
            ((Certifier, 7),),
            ((Regulation, 5),),
            ((Rule, 5),),
            ((Attachment, 50),),
        ]

    def test_excludes_findings_when_certification_is_archived_by_default(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            certification_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        findings = get_findings(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
        )

        assert findings == []

    def test_archived_attachment_hides_linked_attachment_context_by_default(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.findings._format_findings",
            lambda rows: [
                {
                    "finding_id": row["Finding"].id,
                    "attachment": row["Attachment"],
                }
                for row in rows
            ],
        )

        rows = get_findings(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
        )

        assert rows == [
            {
                "finding_id": 1,
                "attachment": None,
            }
        ]

    def test_archived_attachment_does_not_hide_finding_or_appear_in_context(
        self,
        monkeypatch,
        sqlite_session,
        db_factory,
        attachment_row_factory,
        finding_attachment_row_factory,
    ) -> None:
        db_factory()
        archived_attachment = attachment_row_factory(
            id=51,
            archived_at=datetime.now(UTC),
            archive_reason="obsolete",
        )
        archived_link = finding_attachment_row_factory(
            attachment_id=51,
        )

        sqlite_session.add_all(
            [
                archived_attachment,
                archived_link,
            ]
        )
        sqlite_session.commit()

        def fake_format_findings(rows):
            return [
                {
                    "finding_id": rows[0]["Finding"].id,
                    "attachment_ids": [
                        row["Attachment"].id
                        for row in rows
                        if row["Attachment"] is not None
                    ],
                }
            ]

        monkeypatch.setattr(
            "compliance.services.findings._format_findings",
            fake_format_findings,
        )

        findings = get_findings(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
        )

        assert findings == [
            {
                "finding_id": 1,
                "attachment_ids": [50],
            }
        ]


class TestGetFindingById:
    def test_includes_archived_finding_by_default(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            finding_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.findings._format_findings",
            lambda rows: [row["Finding"].archive_reason for row in rows],
        )
        result = get_finding_by_id(sqlite_session, 1)

        assert result == "closed"

    def test_includes_archived_finding_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_finding_by_id(session, 1, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "sites.archived_at IS NULL" not in str(stmt)
        assert "attachments.archived_at IS NULL" not in str(stmt)


class TestFormatFindings:
    def test_formats_finding_rows(self) -> None:
        rows = [
            finding_row(),
            finding_row(
                Finding=SimpleNamespace(
                    id=2,
                    finding="Incomplete record",
                    archived_at=None,
                    archive_reason=None,
                ),
                Rule=SimpleNamespace(
                    id=6,
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_findings(rows)

        assert result == [
            FindingOut(
                finding_id=1,
                finding="Missing document",
                site_id=71,
                certification_id=100,
                certification_title="USDA Organic",
                certification_resolution_date=date(2026, 4, 15),
                rule_id=5,
                rule_index="7 CFR 205.201",
                rule_title="Organic plan",
                rule_description="Producer must maintain an organic system plan.",
                attachments=[],
                archived_at=None,
                archive_reason=None,
            ),
            FindingOut(
                finding_id=2,
                finding="Incomplete record",
                site_id=71,
                certification_id=100,
                certification_title="USDA Organic",
                certification_resolution_date=date(2026, 4, 15),
                rule_id=6,
                rule_index="7 CFR 205.202",
                rule_title="Land requirements",
                rule_description="Land must meet organic requirements.",
                attachments=[],
                archived_at=None,
                archive_reason=None,
            ),
        ]

    def test_formats_finding_without_attachments(self) -> None:
        result = _format_findings([finding_row()])

        assert result == [
            FindingOut(
                finding_id=1,
                finding="Missing document",
                site_id=71,
                certification_id=100,
                certification_title="USDA Organic",
                certification_resolution_date=date(2026, 4, 15),
                rule_id=5,
                rule_index="7 CFR 205.201",
                rule_title="Organic plan",
                rule_description="Producer must maintain an organic system plan.",
                attachments=[],
                archived_at=None,
                archive_reason=None,
            )
        ]

    def test_groups_attachment_rows_under_one_finding(
        self, attachment_row_factory
    ) -> None:
        rows = [
            finding_row(Attachment=attachment_row_factory()),
            finding_row(Attachment=attachment_row_factory(id=51, file_type="jpg")),
        ]

        result = _format_findings(rows)

        assert len(result) == 1
        assert result[0].finding_id == 1
        assert result[0].attachments == [
            FindingAttachmentOut(
                attachment_id=50,
                file_type="pdf",
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                archived_at=None,
                archive_reason=None,
            ),
            FindingAttachmentOut(
                attachment_id=51,
                file_type="jpg",
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                archived_at=None,
                archive_reason=None,
            ),
        ]

    def test_deduplicates_repeated_attachment_rows(
        self, attachment_row_factory
    ) -> None:
        rows = [
            finding_row(Attachment=attachment_row_factory()),
            finding_row(Attachment=attachment_row_factory()),
        ]

        result = _format_findings(rows)

        assert [attachment.attachment_id for attachment in result[0].attachments] == [
            50
        ]

    def test_returns_empty_list_when_rows_are_empty(self) -> None:
        assert _format_findings([]) == []


class TestBuildFindingOut:
    def test_builds_finding_output_from_nested_row_objects(self) -> None:
        result = _build_finding_out(finding_row())

        assert result == FindingOut(
            finding_id=1,
            finding="Missing document",
            site_id=71,
            certification_id=100,
            certification_title="USDA Organic",
            certification_resolution_date=date(2026, 4, 15),
            rule_id=5,
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
            attachments=[],
            archived_at=None,
            archive_reason=None,
        )

    def test_raises_key_error_when_required_row_object_is_missing(self) -> None:
        row = finding_row()
        del row["Certification"]

        with pytest.raises(KeyError, match="Missing finding output fields"):
            _build_finding_out(row)

    def test_raises_key_error_when_regulation_is_missing(self) -> None:
        row = finding_row()
        del row["Regulation"]

        with pytest.raises(KeyError, match="certification_title"):
            _build_finding_out(row)

    def test_raises_key_error_when_required_rule_field_is_missing(self) -> None:
        row = finding_row(
            Rule=SimpleNamespace(
                id=5,
                rule_index="7 CFR 205.201",
                title="Organic plan",
            )
        )

        with pytest.raises(KeyError, match="rule_description"):
            _build_finding_out(row)


class TestPostFindingArchivedById:
    def test_archives_finding_and_returns_context(self, monkeypatch) -> None:
        session = MagicMock()
        finding = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = finding
        expected = object()

        def fake_get_finding_by_id(session_arg, finding_id, *, include_archived):
            assert session_arg is session
            assert finding_id == 1
            assert include_archived is True
            return expected

        monkeypatch.setattr(
            "compliance.services.findings.get_finding_by_id",
            fake_get_finding_by_id,
        )

        result = post_finding_archived_by_id(
            session, 1, archive_request=ArchiveRequest(archive_reason="resolved")
        )

        assert result is expected
        assert finding.archived_at is not None
        assert finding.archived_at.tzinfo is UTC
        assert finding.archive_reason == "resolved"
        session.get.assert_called_once_with(Finding, 1)
        session.commit.assert_called_once_with()

    def test_returns_none_when_finding_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_finding_archived_by_id(
            session, 1, archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Finding, 1)
        session.commit.assert_not_called()


class TestPostFindingRestoredById:
    def test_restores_finding_and_returns_context(self, monkeypatch) -> None:
        session = MagicMock()
        finding = SimpleNamespace(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="resolved",
        )
        session.get.return_value = finding
        expected = object()

        monkeypatch.setattr(
            "compliance.services.findings.get_finding_by_id",
            lambda session_arg, finding_id, *, include_archived: expected,
        )

        result = post_finding_restored_by_id(session, 1)

        assert result is expected
        assert finding.archived_at is None
        assert finding.archive_reason is None
        session.get.assert_called_once_with(Finding, 1)
        session.commit.assert_called_once_with()

    def test_returns_none_when_finding_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_finding_restored_by_id(session, 1)

        assert result is None
        session.get.assert_called_once_with(Finding, 1)
        session.commit.assert_not_called()


class TestPostFindingArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.findings.get_finding_by_id",
            lambda session_arg, finding_id, *, include_archived: session_arg.get(
                Finding, finding_id
            ),
        )

        archived = post_finding_archived_by_id(
            sqlite_session,
            1,
            archive_request=ArchiveRequest(archive_reason=" duplicate "),
        )
        archived = post_finding_archived_by_id(
            sqlite_session,
            1,
            archive_request=ArchiveRequest(archive_reason=" second "),
        )

        assert archived is not None
        assert archived.archived_at is not None
        assert archived.archive_reason == "duplicate"

        restored = post_finding_restored_by_id(sqlite_session, 1)

        assert restored is not None
        assert restored.archived_at is None
        assert restored.archive_reason is None
