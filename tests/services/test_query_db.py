from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.db.models import Certification, Site
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory
from compliance.services.query_db import (
    _build_finding_history_from_site_attachments,
    _build_finding_history_from_site_history,
    _find_attachment_index,
    _find_cert_index,
    _format_site_attachments,
    _format_site_history,
    get_certification_by_id,
    get_site_attachments_by_id,
    get_site_by_id,
    get_site_history_by_id,
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


def site_attachment_row(**overrides):
    row = {
        "Attachment": SimpleNamespace(
            id=50,
            file_type="pdf",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=date(2026, 4, 3),
            certification_id=100,
        ),
        "Certification": SimpleNamespace(
            site_id=71,
            id=100,
            regulation_id=5,
            inspection_date=date(2026, 4, 1),
        ),
        "Regulation": SimpleNamespace(
            id=5,
            title="USDA Organic",
        ),
        "Finding": SimpleNamespace(
            id=1,
            finding="Missing document",
        ),
        "FindingAttachment": MagicMock(),
        "Rule": SimpleNamespace(
            rule_index="7 CFR 205.201",
            title="Organic plan",
            description="Producer must maintain an organic system plan.",
        ),
    }
    row.update(overrides)
    return row


class TestGetSiteById:
    def test_gets_site_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_site = MagicMock(spec=Site)
        session.get.return_value = expected_site

        result = get_site_by_id(12, session)

        session.get.assert_called_once_with(Site, 12)
        assert result is expected_site

    def test_returns_none_when_site_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_site_by_id(999, session)

        session.get.assert_called_once_with(Site, 999)
        assert result is None


class TestGetCertificationById:
    def test_gets_certification_by_id_from_session(self) -> None:
        session = MagicMock()
        expected_certification = MagicMock(spec=Certification)
        session.get.return_value = expected_certification

        result = get_certification_by_id(42, session)

        session.get.assert_called_once_with(Certification, 42)
        assert result is expected_certification

    def test_returns_none_when_certification_is_not_found(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certification_by_id(999, session)

        session.get.assert_called_once_with(Certification, 999)
        assert result is None


class TestGetSiteHistoryById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_site_history_by_id(71, session)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_site_history_when_query_returns_rows(self) -> None:
        rows = [
            site_history_row(
                finding_id=None,
                finding=None,
                rule_index=None,
                rule_title=None,
                rule_description=None,
            )
        ]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_site_history_by_id(71, session)

        session.execute.assert_called_once()
        assert result == _format_site_history(rows)


class TestGetSiteAttachmentsById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_site_attachments_by_id(71, session)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_site_attachments_when_query_returns_rows(self) -> None:
        rows = [site_attachment_row()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_site_attachments_by_id(71, session)

        session.execute.assert_called_once()
        assert result == _format_site_attachments(rows)


class TestFormatSiteHistory:
    def test_creates_site_history_with_certification_and_finding(self) -> None:
        result = _format_site_history([site_history_row()])

        assert isinstance(result, SiteHistory)
        assert result.site_id == 71
        assert result.inspection_count == 1
        assert result.latest_inspection_date == date(2026, 4, 1)
        assert len(result.certifications) == 1
        assert result.certifications[0].cert_id == 100
        assert len(result.certifications[0].findings) == 1
        assert result.certifications[0].findings[0].finding_id == 1

    def test_appends_findings_to_existing_certification(self) -> None:
        rows = [
            site_history_row(finding_id=1, finding="Missing document"),
            site_history_row(finding_id=2, finding="Incomplete record"),
        ]

        result = _format_site_history(rows)

        assert len(result.certifications) == 1
        assert [
            finding.finding_id for finding in result.certifications[0].findings
        ] == [
            1,
            2,
        ]


class TestFindCertIndex:
    def test_returns_matching_certification_index(self) -> None:
        certifications = [
            CertificationHistory(
                cert_id=100,
                result="Pass",
                resolution_date=None,
                reg_title="USDA Organic",
                reg_description="Organic certification",
                certifier_org_name="Org A",
                inspection_date=None,
            ),
            CertificationHistory(
                cert_id=200,
                result="Fail",
                resolution_date=None,
                reg_title="USDA Organic",
                reg_description="Organic certification",
                certifier_org_name="Org B",
                inspection_date=None,
            ),
        ]

        assert _find_cert_index(200, certifications) == 1

    def test_returns_none_when_certification_is_absent(self) -> None:
        assert _find_cert_index(100, []) is None


class TestBuildFindingHistoryFromSiteHistory:
    def test_builds_finding_history_from_row(self) -> None:
        result = _build_finding_history_from_site_history(site_history_row())

        assert isinstance(result, FindingHistory)
        assert result.finding_id == 1
        assert result.rule_index == "7 CFR 205.201"

    def test_raises_key_error_when_required_finding_field_is_missing(self) -> None:
        row = site_history_row()
        del row["rule_description"]

        with pytest.raises(KeyError, match="Missing finding fields"):
            _build_finding_history_from_site_history(row)


class TestBuildFindingHistoryFromSiteAttachments:
    def test_builds_finding_history_from_nested_row_objects(self) -> None:
        result = _build_finding_history_from_site_attachments(site_attachment_row())

        assert result == FindingHistory(
            finding_id=1,
            finding="Missing document",
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
        )

    def test_raises_key_error_when_required_row_object_is_missing(self) -> None:
        row = site_attachment_row()
        del row["Rule"]

        with pytest.raises(KeyError, match="Missing finding history fields"):
            _build_finding_history_from_site_attachments(row)

    def test_raises_key_error_when_required_finding_history_field_is_missing(
        self,
    ) -> None:
        row = site_attachment_row(
            Rule=SimpleNamespace(
                rule_index="7 CFR 205.201",
                title="Organic plan",
            )
        )

        with pytest.raises(KeyError, match="rule_description"):
            _build_finding_history_from_site_attachments(row)


class TestFormatSiteAttachments:
    def test_creates_site_attachments_with_finding_link(self) -> None:
        result = _format_site_attachments([site_attachment_row()])

        assert result.site_id == 71
        assert len(result.attachments) == 1
        assert result.attachments[0].id == 50
        assert result.attachments[0].regulation_title == "USDA Organic"
        assert len(result.attachments[0].finding_links) == 1
        assert result.attachments[0].finding_links[0].finding_id == 1

    def test_groups_multiple_findings_under_same_attachment(self) -> None:
        rows = [
            site_attachment_row(),
            site_attachment_row(
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_site_attachments(rows)

        assert len(result.attachments) == 1
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_raises_stop_iteration_when_rows_are_empty(self) -> None:
        with pytest.raises(StopIteration):
            _format_site_attachments([])

    def test_raises_value_error_when_first_row_is_empty(self) -> None:
        with pytest.raises(ValueError, match="First attachment row is empty"):
            _format_site_attachments([{}])


class TestFindAttachmentIndex:
    def test_returns_matching_attachment_index(self) -> None:
        attachments = [{"id": 10}, {"id": 20}]

        assert _find_attachment_index(20, attachments) == 1

    def test_returns_none_when_attachment_is_absent(self) -> None:
        assert _find_attachment_index(20, [{"id": 10}]) is None
