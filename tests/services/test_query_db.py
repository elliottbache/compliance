from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentWithContextOut,
    CertificationAttachmentsOut,
    ClientInOut,
    FindingOut,
)
from compliance.db.models import Certification, Client, Site
from compliance.schemas import FindingHistory, SiteHistory
from compliance.services.query_db import (
    AttachmentCertificationNotFoundError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    _build_finding_history_from_site_attachments,
    _build_finding_history_from_site_history,
    _build_finding_out,
    _format_attachment,
    _format_certification_attachments,
    _format_findings,
    _format_new_attachment_with_context,
    _format_site_attachments,
    _format_site_history,
    get_attachment_by_id,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications_by_site_id,
    get_site_attachments_by_id,
    get_site_by_id,
    get_site_history_by_id,
    post_new_attachment,
    post_new_client,
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


class TestGetCertificationsBySiteId:
    def test_returns_certifications_for_site(self) -> None:
        session = MagicMock()
        expected_certifications = [
            MagicMock(spec=Certification),
            MagicMock(spec=Certification),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = (
            expected_certifications
        )

        result = get_certifications_by_site_id(12, session, limit=None, offset=0)

        session.execute.assert_called_once()
        assert result == expected_certifications

    def test_returns_empty_list_when_site_has_no_certifications(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        result = get_certifications_by_site_id(999, session, limit=None, offset=0)

        session.execute.assert_called_once()
        assert result == []

    def test_orders_certifications_by_resolution_date_desc_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [
            MagicMock(spec=Certification)
        ]

        get_certifications_by_site_id(12, session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY certifications.resolution_date DESC, certifications.id" in str(
            stmt
        )

    def test_applies_limit_and_offset_to_query(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = [
            MagicMock(spec=Certification)
        ]

        get_certifications_by_site_id(12, session, limit=10, offset=20)

        stmt = session.execute.call_args.args[0]
        statement_text = str(stmt)
        assert "LIMIT" in statement_text
        assert "OFFSET" in statement_text


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


class TestGetSiteAttachmentsOutById:
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


class TestGetAttachmentById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_attachment_when_query_returns_rows(self) -> None:
        rows = [site_attachment_row()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result == _format_attachment(rows)


class TestGetCertificationAttachmentsById:
    def test_returns_none_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = get_certification_attachments_by_id(100, session)

        session.get.assert_called_once_with(Certification, 100)
        session.execute.assert_not_called()
        assert result is None

    def test_returns_empty_attachment_list_when_certification_has_no_attachments(
        self,
    ) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certification)
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_certification_attachments_by_id(100, session)

        session.get.assert_called_once_with(Certification, 100)
        session.execute.assert_called_once()
        assert result == CertificationAttachmentsOut(
            certification_id=100,
            attachments=[],
        )

    def test_formats_certification_attachments_when_query_returns_rows(self) -> None:
        rows = [site_attachment_row()]
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certification)
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_certification_attachments_by_id(100, session)

        session.get.assert_called_once_with(Certification, 100)
        session.execute.assert_called_once()
        assert result == _format_certification_attachments(rows)

    def test_orders_attachments_by_attachment_id_then_finding_id(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Certification)
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_certification_attachments_by_id(100, session)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY attachments.id, findings.id" in str(stmt)


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


class TestPostNewClient:
    def test_adds_and_commits_new_client(self) -> None:
        session = MagicMock()
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        post_new_client(client, session)

        session.add.assert_called_once()
        added_client = session.add.call_args.args[0]

        assert isinstance(added_client, Client)
        assert added_client.nif == "A1234567B"
        assert added_client.company_name == "Acme Compliance"
        assert added_client.contact_name == "Ada Lovelace"
        assert added_client.email == "ada@example.com"
        assert added_client.telephone == 123456789

    def test_rolls_back_and_returns_none_when_insert_conflicts(self) -> None:
        session = MagicMock()
        session.commit.side_effect = IntegrityError("insert failed", {}, None)
        client = ClientInOut(
            nif="A1234567B",
            company_name="Acme Compliance",
            contact_name="Ada Lovelace",
            email="ada@example.com",
            telephone=123456789,
        )

        result = post_new_client(client, session)

        assert result is None
        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()


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

    def test_groups_certifications_by_id_without_reordering(self) -> None:
        rows = [
            site_history_row(cert_id=200, finding_id=2, finding="Second cert finding"),
            site_history_row(cert_id=100, finding_id=1, finding="First cert finding"),
            site_history_row(
                cert_id=200,
                finding_id=3,
                finding="Another second cert finding",
            ),
        ]

        result = _format_site_history(rows)

        assert [cert.cert_id for cert in result.certifications] == [200, 100]
        assert [
            finding.finding_id for finding in result.certifications[0].findings
        ] == [2, 3]


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


class TestBuildFindingHistoryFromSiteAttachmentsOut:
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
    def test_creates_attachment_without_finding_links(self) -> None:
        rows = [site_attachment_row(Finding=None, Rule=None)]

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

    def test_collects_two_finding_links_for_attachment(self) -> None:
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

        result = _format_attachment(rows)

        assert result.id == 50
        assert [finding.finding_id for finding in result.finding_links] == [1, 2]
        assert [finding.rule_index for finding in result.finding_links] == [
            "7 CFR 205.201",
            "7 CFR 205.202",
        ]


class TestFormatSiteAttachmentsOut:
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

    def test_groups_attachments_by_id_without_reordering(self) -> None:
        second_attachment = SimpleNamespace(
            id=60,
            file_type="pdf",
            file_path="dummy/second.pdf",
            description="Second attachment",
            uploaded_at=date(2026, 4, 4),
            certification_id=100,
        )
        rows = [
            site_attachment_row(Attachment=second_attachment),
            site_attachment_row(),
            site_attachment_row(
                Attachment=second_attachment,
                Finding=SimpleNamespace(id=2, finding="Incomplete record"),
                Rule=SimpleNamespace(
                    rule_index="7 CFR 205.202",
                    title="Land requirements",
                    description="Land must meet organic requirements.",
                ),
            ),
        ]

        result = _format_site_attachments(rows)

        assert [attachment.id for attachment in result.attachments] == [60, 50]
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_raises_stop_iteration_when_rows_are_empty(self) -> None:
        with pytest.raises(StopIteration):
            _format_site_attachments([])

    def test_raises_value_error_when_first_row_is_empty(self) -> None:
        with pytest.raises(ValueError, match="First attachment row is empty"):
            _format_site_attachments([{}])


class TestFormatCertificationAttachmentsOut:
    def test_creates_certification_attachments_with_finding_link(self) -> None:
        result = _format_certification_attachments([site_attachment_row()])

        assert result.certification_id == 100
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

        result = _format_certification_attachments(rows)

        assert len(result.attachments) == 1
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_groups_attachments_by_id_without_reordering(self) -> None:
        second_attachment = SimpleNamespace(
            id=60,
            file_type="pdf",
            file_path="dummy/second.pdf",
            description="Second attachment",
            uploaded_at=date(2026, 4, 4),
            certification_id=100,
        )
        rows = [
            site_attachment_row(Attachment=second_attachment),
            site_attachment_row(),
            site_attachment_row(
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
