from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
)
from compliance.db.models import Certification, Site
from compliance.services.certifications import (
    CertificationCertifierError,
    CertificationConflictError,
    CertificationRegulationError,
    CertificationSiteError,
    _format_certification_attachments,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications,
    post_new_certification,
)


def _certification(**overrides) -> Certification:
    certification = Certification(
        id=42,
        certifier_id=7,
        regulation_id=3,
        site_id=12,
        result="Pass",
        inspection_date=date(2026, 4, 1),
        resolution_date=None,
    )
    for key, value in overrides.items():
        setattr(certification, key, value)
    return certification


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
    def test_returns_certifications_from_session(self) -> None:
        session = MagicMock()
        certifications = [
            _certification(id=42),
            _certification(id=43, regulation_id=4),
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
        assert "WHERE certifications.site_id = :site_id_1" in str(stmt)

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

    def test_formats_certification_attachments_when_query_returns_rows(
        self, site_attachment_row_factory
    ) -> None:
        rows = [site_attachment_row_factory()]
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


class TestPostNewCertification:
    def test_adds_and_commits_new_certification(self) -> None:
        session = MagicMock()
        certification = _certification_create()

        result = post_new_certification(certification, session)

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
            post_new_certification(certification, session)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_certifier_error_when_certifier_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error(
            "certifications_certifier_id_fkey"
        )

        with pytest.raises(CertificationCertifierError):
            post_new_certification(_certification_create(), session)

        session.rollback.assert_called_once_with()

    def test_raises_regulation_error_when_regulation_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error(
            "certifications_regulation_id_fkey"
        )

        with pytest.raises(CertificationRegulationError):
            post_new_certification(_certification_create(), session)

        session.rollback.assert_called_once_with()

    def test_raises_site_error_when_site_does_not_exist(self) -> None:
        session = MagicMock()
        session.commit.side_effect = _integrity_error("certifications_site_id_fkey")

        with pytest.raises(CertificationSiteError):
            post_new_certification(_certification_create(), session)

        session.rollback.assert_called_once_with()


class TestFormatCertificationAttachmentsOut:
    def test_creates_certification_attachments_with_finding_link(
        self, site_attachment_row_factory
    ) -> None:
        result = _format_certification_attachments([site_attachment_row_factory()])

        assert result.certification_id == 100
        assert len(result.attachments) == 1
        assert result.attachments[0].id == 50
        assert result.attachments[0].regulation_title == "USDA Organic"
        assert len(result.attachments[0].finding_links) == 1
        assert result.attachments[0].finding_links[0].finding_id == 1

    def test_groups_multiple_findings_under_same_attachment(
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

        result = _format_certification_attachments(rows)

        assert len(result.attachments) == 1
        assert [
            finding.finding_id for finding in result.attachments[0].finding_links
        ] == [1, 2]

    def test_groups_attachments_by_id_without_reordering(
        self, site_attachment_row_factory
    ) -> None:
        second_attachment = SimpleNamespace(
            id=60,
            file_type="pdf",
            file_path="dummy/second.pdf",
            description="Second attachment",
            uploaded_at=date(2026, 4, 4),
            certification_id=100,
        )
        rows = [
            site_attachment_row_factory(Attachment=second_attachment),
            site_attachment_row_factory(),
            site_attachment_row_factory(
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
