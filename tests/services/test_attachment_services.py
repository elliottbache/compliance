from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from compliance.api.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.db.models import (
    Attachment,
    Base,
    Certification,
    Certifier,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.services._helpers import _format_attachment
from compliance.services.attachments import (
    AttachmentCertificationNotFoundError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    _format_attachments,
    _format_new_attachment_with_context,
    get_attachment_by_id,
    get_attachments,
    post_attachment_archived_by_id,
    post_attachment_restored_by_id,
    post_new_attachment,
)


class TestGetAttachments:
    def test_returns_formatted_attachments_from_session(
        self, attachment_out_factory
    ) -> None:
        rows = [attachment_out_factory()]
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

    def test_excludes_archived_attachments_by_default(
        self,
        sqlite_session,
        monkeypatch,
        client_row_factory,
        site_row_factory,
        certification_row_factory,
        rule_row_factory,
        regulation_row_factory,
        finding_row_factory,
        attachment_row_factory,
    ) -> None:
        client = client_row_factory()
        site = site_row_factory(
            id=71,
        )
        certifier = Certifier(id=7, organization_name="SafeCheck Inc.")
        regulation = regulation_row_factory(
            id=5,
        )
        certification = certification_row_factory(
            id=100,
            certifier_id=7,
            regulation_id=5,
            site_id=71,
        )
        active = attachment_row_factory()
        archived = attachment_row_factory(
            id=51,
            archived_at=datetime.now(UTC),
            archive_reason="obsolete",
        )
        sqlite_session.add_all(
            [client, site, certifier, regulation, certification, active, archived]
        )
        sqlite_session.commit()
        monkeypatch.setattr(
            "compliance.services.attachments._format_attachments",
            lambda rows: [row["Attachment"].id for row in rows],
        )

        attachment_ids = get_attachments(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        assert attachment_ids == [50]

    def test_filters_optional_archive_links_in_outer_join_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachments(
            session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        statement_text = str(session.execute.call_args.args[0])

        assert "LEFT OUTER JOIN findings" in statement_text
        assert "findings.archived_at IS NULL" in statement_text
        assert "LEFT OUTER JOIN rules" in statement_text
        assert "rules.archived_at IS NULL" in statement_text
        assert "AND (findings.id IS NULL" not in statement_text
        assert "AND (rules.id IS NULL" not in statement_text

    def test_includes_archived_attachments_when_requested(
        self,
        sqlite_session,
        monkeypatch,
        client_row_factory,
        site_row_factory,
        certification_row_factory,
        regulation_row_factory,
        attachment_row_factory,
    ) -> None:
        client = client_row_factory()
        site = site_row_factory(id=71)
        certifier = Certifier(id=7, organization_name="SafeCheck Inc.")
        regulation = regulation_row_factory(id=5)
        certification = certification_row_factory(
            id=100,
            certifier_id=7,
            regulation_id=5,
            site_id=71,
            archived_at=datetime.now(UTC),
            archive_reason="superseded",
        )

        active = attachment_row_factory()
        archived = attachment_row_factory(
            id=51,
            archived_at=datetime.now(UTC),
            archive_reason="obsolete",
        )
        sqlite_session.add_all(
            [client, site, certifier, regulation, certification, active, archived]
        )
        sqlite_session.commit()
        monkeypatch.setattr(
            "compliance.services.attachments._format_attachments",
            lambda rows: [row["Attachment"].id for row in rows],
        )

        attachment_ids = get_attachments(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
            include_archived=True,
        )

        assert set(attachment_ids) == {50, 51}

    def test_archived_finding_does_not_appear_in_attachment_context_or_finding_ids(
        self,
        sqlite_session,
        monkeypatch,
        client_row_factory,
        site_row_factory,
        certification_row_factory,
        rule_row_factory,
        regulation_row_factory,
        finding_row_factory,
        attachment_row_factory,
    ) -> None:
        client = client_row_factory()
        site = site_row_factory(id=71)
        certifier = Certifier(id=7, organization_name="SafeCheck Inc.")
        regulation = regulation_row_factory(id=5)
        rule = rule_row_factory(id=5, regulation_id=5)
        certification = certification_row_factory(
            id=100,
            certifier_id=7,
            regulation_id=5,
            site_id=71,
        )
        active_finding = finding_row_factory(
            id=1,
            certification_id=100,
            rule_id=5,
        )
        archived_finding = finding_row_factory(
            id=2,
            certification_id=100,
            rule_id=5,
            archived_at=datetime.now(UTC),
            archive_reason="resolved",
        )
        attachment = attachment_row_factory(
            id=50,
            certification_id=100,
        )
        active_link = FindingAttachment(
            finding_id=1,
            attachment_id=50,
            certification_id=100,
        )
        archived_link = FindingAttachment(
            finding_id=2,
            attachment_id=50,
            certification_id=100,
        )

        sqlite_session.add_all(
            [
                client,
                site,
                certifier,
                regulation,
                rule,
                certification,
                active_finding,
                archived_finding,
                attachment,
                active_link,
                archived_link,
            ]
        )
        sqlite_session.commit()

        def fake_format_attachments(rows):
            return [
                {
                    "attachment_id": rows[0]["Attachment"].id,
                    "finding_ids": [
                        row["Finding"].id for row in rows if row["Finding"] is not None
                    ],
                    "has_archived_finding_context": any(
                        row["Finding"] is not None and row["Finding"].id == 2
                        for row in rows
                    ),
                }
            ]

        monkeypatch.setattr(
            "compliance.services.attachments._format_attachments",
            fake_format_attachments,
        )

        attachments = get_attachments(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        assert attachments == [
            {
                "attachment_id": 50,
                "finding_ids": [1],
                "has_archived_finding_context": False,
            }
        ]


class TestFormatAttachments:
    def test_formats_attachment_without_finding_ids(
        self, attachment_out_factory
    ) -> None:
        result = _format_attachments([attachment_out_factory(Finding=None)])

        assert result == [
            AttachmentOut(
                id=50,
                file_type="pdf",
                file_name="evidence",
                certification_id=100,
                description="Inspection evidence",
                finding_ids=[],
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
                inspection_date=date(2026, 4, 1),
                regulation_id=5,
                regulation_title="USDA Organic",
                archived_at=None,
                archive_reason=None,
            )
        ]

    def test_groups_finding_ids_under_one_attachment(
        self, attachment_out_factory
    ) -> None:
        rows = [
            attachment_out_factory(),
            attachment_out_factory(Finding=SimpleNamespace(id=2)),
        ]

        result = _format_attachments(rows)

        assert len(result) == 1
        assert result[0].finding_ids == [1, 2]

    def test_deduplicates_repeated_finding_ids(self, attachment_out_factory) -> None:
        rows = [
            attachment_out_factory(),
            attachment_out_factory(),
        ]

        result = _format_attachments(rows)

        assert result[0].finding_ids == [1]


class TestGetAttachmentById:
    def test_returns_none_when_query_returns_no_rows(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        result = get_attachment_by_id(session, 50)

        session.execute.assert_called_once()
        assert result is None

    def test_formats_attachment_when_query_returns_rows(
        self, attachment_out_factory
    ) -> None:
        rows = [attachment_out_factory()]
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = rows

        result = get_attachment_by_id(session, 50)

        session.execute.assert_called_once()
        assert result == _format_attachment(rows)

    def test_excludes_archived_attachment_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(session, 50)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "JOIN sites" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)

    def test_filters_optional_archive_links_in_outer_join_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(session, 50)

        statement_text = str(session.execute.call_args.args[0])

        assert "LEFT OUTER JOIN findings" in statement_text
        assert "findings.archived_at IS NULL" in statement_text
        assert "LEFT OUTER JOIN rules" in statement_text
        assert "rules.archived_at IS NULL" in statement_text
        assert "AND (findings.id IS NULL" not in statement_text
        assert "AND (rules.id IS NULL" not in statement_text

    def test_includes_archived_attachment_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(session, 50, include_archived=True)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" not in str(stmt)
        assert "sites.archived_at IS NULL" not in str(stmt)
        assert "findings.archived_at IS NULL" not in str(stmt)
        assert "rules.archived_at IS NULL" not in str(stmt)


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
            post_new_attachment(session, attachment)

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
            post_new_attachment(session, attachment)

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
            post_new_attachment(session, attachment)

        session.add.assert_not_called()


class TestFormatNewAttachmentWithContext:
    def test_builds_attachment_output_with_certification_context(self) -> None:
        attachment = SimpleNamespace(
            id=50,
            file_type="pdf",
            certification_id=100,
            file_path="/path/placeholder/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
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
        self, attachment_out_factory
    ) -> None:
        rows = [attachment_out_factory(Finding=None, Rule=None)]

        result = _format_attachment(rows)

        assert result == AttachmentWithContextOut(
            id=50,
            file_type="pdf",
            file_path="dummy/evidence.pdf",
            description="Inspection evidence",
            uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            archived_at=None,
            archive_reason=None,
            certification_id=100,
            inspection_date=date(2026, 4, 1),
            regulation_id=5,
            regulation_title="USDA Organic",
            finding_links=[],
        )

    def test_collects_two_finding_links_for_attachment(
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

        result = _format_attachment(rows)

        assert result.id == 50
        assert [finding.finding_id for finding in result.finding_links] == [1, 2]
        assert [finding.rule_index for finding in result.finding_links] == [
            "7 CFR 205.201",
            "7 CFR 205.202",
        ]


class TestPostAttachmentArchivedById:
    def test_archives_attachment_and_returns_context(self, monkeypatch) -> None:
        session = MagicMock()
        attachment = SimpleNamespace(archived_at=None, archive_reason=None)
        session.get.return_value = attachment
        expected = object()

        def fake_get_attachment_by_id(session_arg, attachment_id, *, include_archived):
            assert session_arg is session
            assert attachment_id == 50
            assert include_archived is True
            return expected

        monkeypatch.setattr(
            "compliance.services.attachments.get_attachment_by_id",
            fake_get_attachment_by_id,
        )

        result = post_attachment_archived_by_id(
            session, 50, archive_request=ArchiveRequest(archive_reason="old file")
        )

        assert result is expected
        assert attachment.archived_at is not None
        assert attachment.archived_at.tzinfo is UTC
        assert attachment.archive_reason == "old file"
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_called_once_with()

    def test_returns_none_when_attachment_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_attachment_archived_by_id(
            session, 50, archive_request=ArchiveRequest()
        )

        assert result is None
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_not_called()


class TestPostAttachmentRestoredById:
    def test_restores_attachment_and_returns_context(self, monkeypatch) -> None:
        session = MagicMock()
        attachment = SimpleNamespace(
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old file",
        )
        session.get.return_value = attachment
        expected = object()

        monkeypatch.setattr(
            "compliance.services.attachments.get_attachment_by_id",
            lambda session_arg, attachment_id, *, include_archived: expected,
        )

        result = post_attachment_restored_by_id(session, 50)

        assert result is expected
        assert attachment.archived_at is None
        assert attachment.archive_reason is None
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_called_once_with()

    def test_returns_none_when_attachment_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_attachment_restored_by_id(session, 50)

        assert result is None
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_not_called()


class TestPostAttachmentArchiveRestoreIntegration:
    def test_archive_then_restore_works(self, monkeypatch) -> None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)

        with Session(engine) as session:
            client = Client(
                nif="A1234567B",
                company_name="Acme Compliance",
                contact_name="Ada Lovelace",
                email=None,
                telephone=None,
            )
            site = Site(
                id=71,
                nif="A1234567B",
                city="Madrid",
                postal_code=28013,
                street="Gran Via",
                street_number=None,
                suite=None,
                address_info=None,
            )
            certifier = Certifier(id=7, organization_name="SafeCheck Inc.")
            regulation = Regulation(
                id=5,
                title="USDA Organic",
                description="Organic handling requirements.",
                published_date=date(2026, 1, 15),
            )
            certification = Certification(
                id=100,
                certifier_id=7,
                regulation_id=5,
                site_id=71,
                result="Pass",
                inspection_date=date(2026, 4, 1),
                resolution_date=date(2026, 4, 15),
            )
            attachment = Attachment(
                id=50,
                file_type="pdf",
                certification_id=100,
                file_path="dummy/evidence.pdf",
                description="Inspection evidence",
                uploaded_at=datetime(2026, 4, 3, 9, 30, tzinfo=UTC),
            )
            session.add(client)
            session.add(site)
            session.add(certifier)
            session.add(regulation)
            session.add(certification)
            session.add(attachment)
            session.commit()
            monkeypatch.setattr(
                "compliance.services.attachments.get_attachment_by_id",
                lambda session_arg, attachment_id, *, include_archived: session_arg.get(
                    Attachment, attachment_id
                ),
            )

            archived = post_attachment_archived_by_id(
                session,
                50,
                archive_request=ArchiveRequest(archive_reason=" duplicate "),
            )
            archived = post_attachment_archived_by_id(
                session,
                50,
                archive_request=ArchiveRequest(archive_reason=" second "),
            )

            assert archived is not None
            assert archived.archived_at is not None
            assert archived.archive_reason == "duplicate"

            restored = post_attachment_restored_by_id(session, 50)

            assert restored is not None
            assert restored.archived_at is None
            assert restored.archive_reason is None
