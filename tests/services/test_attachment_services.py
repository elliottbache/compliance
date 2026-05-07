from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.db.models import Certification, Finding, Rule, Site
from compliance.services._helpers import _format_attachment
from compliance.services.attachments import (
    AttachmentCertificationNotFoundError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    _format_attachments,
    _format_new_attachment_with_context,
    get_attachment_by_id,
    get_attachments,
    post_new_attachment,
)


class TestGetAttachments:
    def test_returns_formatted_attachments_from_session(
        self, attachment_row_factory
    ) -> None:
        rows = [attachment_row_factory()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_attachments(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        assert result == _format_attachments(rows)

    def test_checks_filter_parent_records_before_querying(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            MagicMock(spec=Site),
            MagicMock(spec=Certification),
            MagicMock(spec=Rule),
            MagicMock(spec=Finding),
        ]
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachments(
            session,
            site_id=71,
            certification_id=100,
            rule_id=5,
            finding_id=1,
        )

        assert session.get.call_args_list == [
            ((Site, 71),),
            ((Certification, 100),),
            ((Rule, 5),),
            ((Finding, 1),),
        ]

    def test_filters_by_finding_id_when_finding_exists(self) -> None:
        session = MagicMock()
        session.get.return_value = MagicMock(spec=Finding)
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachments(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=1,
        )

        stmt = session.execute.call_args.args[0]

        session.get.assert_called_once_with(Finding, 1)
        assert "finding_attachments.finding_id = :finding_id_1" in str(stmt)

    def test_excludes_archived_attachments_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachments(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)

    def test_includes_archived_attachments_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachments(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
            include_archived=True,
        )

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" not in str(stmt)


class TestFormatAttachments:
    def test_formats_attachment_without_finding_ids(
        self, attachment_row_factory
    ) -> None:
        result = _format_attachments([attachment_row_factory(Finding=None)])

        assert result == [
            AttachmentOut(
                id=50,
                file_type="pdf",
                file_name="evidence",
                certification_id=100,
                description="Inspection evidence",
                finding_ids=[],
                uploaded_at=date(2026, 4, 3),
                inspection_date=date(2026, 4, 1),
                regulation_id=5,
                regulation_title="USDA Organic",
            )
        ]

    def test_groups_finding_ids_under_one_attachment(
        self, attachment_row_factory
    ) -> None:
        rows = [
            attachment_row_factory(),
            attachment_row_factory(Finding=SimpleNamespace(id=2)),
        ]

        result = _format_attachments(rows)

        assert len(result) == 1
        assert result[0].finding_ids == [1, 2]

    def test_deduplicates_repeated_finding_ids(self, attachment_row_factory) -> None:
        rows = [
            attachment_row_factory(),
            attachment_row_factory(),
        ]

        result = _format_attachments(rows)

        assert result[0].finding_ids == [1]


class TestGetAttachmentById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_attachment_when_query_returns_rows(
        self, attachment_row_factory
    ) -> None:
        rows = [attachment_row_factory()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_attachment_by_id(50, session)

        session.execute.assert_called_once()
        assert result == _format_attachment(rows)

    def test_excludes_archived_attachment_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(50, session)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)

    def test_includes_archived_attachment_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(50, session, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" not in str(stmt)


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


class TestFormatAttachment:
    def test_creates_attachment_without_finding_links(
        self, attachment_row_factory
    ) -> None:
        rows = [attachment_row_factory(Finding=None, Rule=None)]

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
        self, attachment_row_factory
    ) -> None:
        rows = [
            attachment_row_factory(),
            attachment_row_factory(
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
