from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentWithContextOut,
    FindingOut,
)
from compliance.services.findings import (
    _build_finding_out,
    _format_findings,
)
from compliance.services.records import (
    AttachmentCertificationNotFoundError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    _format_attachment,
    _format_new_attachment_with_context,
    get_attachment_by_id,
    post_new_attachment,
)


def site_history_row(**overrides):
    row = {
        "site_id": 71,
        "cert_id": 100,
        "result": "Pass",
        "resolution_date": None,
        "reg_title": "USDA Organic",
        "reg_description": "Organic certification",
        "certifier_org_name": "Org A",
        "inspection_date": date(2026, 4, 1),
        "finding_id": 1,
        "finding": "Missing document",
        "rule_index": "7 CFR 205.201",
        "rule_title": "Organic plan",
        "rule_description": "Producer must maintain an organic system plan.",
    }
    row.update(overrides)
    return row


def finding_row(**overrides):
    row = {
        "Finding": SimpleNamespace(
            id=1,
            finding="Missing document",
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
    }
    row.update(overrides)
    return row


class TestGetAttachmentById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_attachment_when_query_returns_rows(
        self, site_attachment_row_factory
    ) -> None:
        rows = [site_attachment_row_factory()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result == _format_attachment(rows)


class TestPostNewAttachment:
    def test_raises_when_certification_does_not_exist(self) -> None:
        attachment = AttachmentCreate(
            file_type="pdf",
            file_name="evidence",
            certification_id=100,
        )
        session = MagicMock()
        session.get.return_value = None

        with pytest.raises(
            AttachmentCertificationNotFoundError,
            match="Certification 100 does not exist",
        ):
            post_new_attachment(attachment, session)

        session.add.assert_not_called()

    def test_raises_when_finding_does_not_exist(self) -> None:
        attachment = AttachmentCreate(
            file_type="pdf",
            file_name="evidence",
            certification_id=100,
            finding_ids=[7],
        )
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=100, inspection_date=date(2026, 4, 1)),
            None,
        ]

        with pytest.raises(
            AttachmentFindingNotFoundError,
            match="Finding 7 does not exist",
        ):
            post_new_attachment(attachment, session)

        session.add.assert_not_called()

    def test_raises_when_finding_belongs_to_another_certification(self) -> None:
        attachment = AttachmentCreate(
            file_type="pdf",
            file_name="evidence",
            certification_id=100,
            finding_ids=[7],
        )
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=100, inspection_date=date(2026, 4, 1)),
            SimpleNamespace(id=7, certification_id=200),
        ]

        with pytest.raises(
            AttachmentFindingCertificationMismatchError,
            match="Finding 7 does not belong to certification 100",
        ):
            post_new_attachment(attachment, session)

        session.add.assert_not_called()


class TestFormatNewAttachmentWithContext:
    def test_builds_attachment_output_with_certification_context(self) -> None:
        attachment = SimpleNamespace(
            id=50,
            file_type="pdf",
            certification_id=100,
            file_path="/path/placeholder/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=date(2026, 4, 3),
        )
        certification = SimpleNamespace(
            inspection_date=date(2026, 4, 1),
            regulation_id=5,
            certification_regulation_rel=SimpleNamespace(title="USDA Organic"),
        )

        result = _format_new_attachment_with_context(
            attachment,
            certification,
            [1, 2],
        )

        assert result.id == 50
        assert result.file_name == "evidence"
        assert result.finding_ids == [1, 2]
        assert result.inspection_date == date(2026, 4, 1)
        assert result.regulation_id == 5
        assert result.regulation_title == "USDA Organic"


class TestFormatFindings:
    def test_formats_finding_rows(self) -> None:
        rows = [
            finding_row(),
            finding_row(
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
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
            ),
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


class TestFormatAttachment:
    def test_creates_attachment_without_finding_links(
        self, site_attachment_row_factory
    ) -> None:
        rows = [site_attachment_row_factory(Finding=None, Rule=None)]

        result = _format_attachment(rows)

        assert result == AttachmentWithContextOut(
            id=50,
            file_type="pdf",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=date(2026, 4, 3),
            certification_id=100,
            inspection_date=date(2026, 4, 1),
            regulation_id=5,
            regulation_title="USDA Organic",
            finding_links=[],
        )

    def test_collects_two_finding_links_for_attachment(
        self, site_attachment_row_factory
    ) -> None:
        rows = [
            site_attachment_row_factory(),
            site_attachment_row_factory(
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_attachment(rows)

        assert result.id == 50
        assert [finding.finding_id for finding in result.finding_links] == [1, 2]
        assert [finding.rule_index for finding in result.finding_links] == [
            "7 CFR 205.201",
            "7 CFR 205.202",
        ]
