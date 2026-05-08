from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.api.schemas import FindingAttachmentOut, FindingOut
from compliance.db.models import (
    Attachment,
    Certification,
    Rule,
    Site,
)
from compliance.services.findings import (
    _build_finding_out,
    _format_findings,
    get_finding_by_id,
    get_findings,
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


def attachment(**overrides):
    data = {
        "id": 50,
        "file_type": "pdf",
        "file_path": "dummy/evidence.pdf",
        "description": "Inspection evidence",
        "uploaded_at": datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
        "archived_at": None,
        "archive_reason": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


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

    def test_excludes_archived_findings_by_default(self) -> None:
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
        assert "findings.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "AND (attachments.id IS NULL" not in str(stmt)

    def test_includes_archived_findings_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_findings(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            attachment_id=None,
            open_only=False,
            include_archived=True,
        )

        stmt = session.execute.call_args.args[0]
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "sites.archived_at IS NULL" not in str(stmt)
        assert "attachments.archived_at IS NULL" not in str(stmt)

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
            MagicMock(spec=Site),
            MagicMock(spec=Certification),
            MagicMock(spec=Rule),
            MagicMock(spec=Attachment),
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
            ((Rule, 5),),
            ((Attachment, 50),),
        ]


class TestGetFindingById:
    def test_excludes_archived_finding_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_finding_by_id(1, session)

        stmt = session.execute.call_args.args[0]
        assert "findings.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "AND (attachments.id IS NULL" not in str(stmt)

    def test_includes_archived_finding_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_finding_by_id(1, session, include_archived=True)

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

    def test_groups_attachment_rows_under_one_finding(self) -> None:
        rows = [
            finding_row(Attachment=attachment(id=50)),
            finding_row(Attachment=attachment(id=51, file_type="jpg")),
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

    def test_deduplicates_repeated_attachment_rows(self) -> None:
        rows = [
            finding_row(Attachment=attachment(id=50)),
            finding_row(Attachment=attachment(id=50)),
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
