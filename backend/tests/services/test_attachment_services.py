import re
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import clamd
import pytest
from compliance.db.models import (
    Attachment,
    Certification,
    Finding,
    Role,
    Rule,
    Site,
    User,
)
from compliance.services.attachments import (
    _UPLOAD_DIR,
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentCreateError,
    AttachmentFileError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    AttachmentInfectedError,
    AttachmentNotFoundError,
    AttachmentPermissionError,
    AttachmentScanError,
    AttachmentScannerUnavailableError,
    AttachmentTooLargeError,
    AttachmentUnsupportedMediaTypeError,
    _format_attachments,
    _format_new_attachment_with_context,
    _validate_file_size_type_and_ext,
    check_attachment_storage,
    get_attachment_by_id,
    get_attachment_download,
    get_attachments,
    post_attachment_archived_by_id,
    post_attachment_restored_by_id,
    post_attachment_upload,
    post_new_attachment,
)
from compliance.services.attachments.files import ClamAVFileScanner, NoOpFileScanner
from compliance.services.attachments.formatting import format_attachment
from compliance.services.lifecycle import LifecycleResult
from compliance.services.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from sqlalchemy.exc import IntegrityError


def _upload_stream(content: bytes = b"%PDF-1.4\n") -> BytesIO:
    return BytesIO(content)


def _install_fake_clamav_client(monkeypatch, fake_client) -> None:
    monkeypatch.setattr(
        "compliance.services.attachments.files.clamd.ClamdNetworkSocket",
        lambda **kwargs: fake_client,
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
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.attachments.crud._format_attachments",
            lambda rows: [row["Attachment"].id for row in rows],
        )

        attachment_ids = get_attachments(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        assert attachment_ids == []

    def test_excludes_attachments_for_archived_client_by_default(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            client_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.attachments.crud._format_attachments",
            lambda rows: [row["Attachment"].id for row in rows],
        )

        attachment_ids = get_attachments(
            sqlite_session,
            site_id=None,
            certification_id=None,
            rule_id=None,
            finding_id=None,
        )

        assert attachment_ids == []

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
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.attachments.crud._format_attachments",
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

        assert set(attachment_ids) == {50}

    def test_archived_finding_does_not_appear_in_attachment_context_or_finding_ids(
        self,
        monkeypatch,
        sqlite_session,
        db_factory,
        finding_row_factory,
        finding_attachment_row_factory,
        archived_fields,
    ) -> None:
        db_factory()

        archived_finding = finding_row_factory(
            id=2,
            **archived_fields("resolved"),
        )
        archived_link = finding_attachment_row_factory(
            finding_id=2,
        )

        sqlite_session.add_all(
            [
                archived_finding,
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
            "compliance.services.attachments.crud._format_attachments",
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
                file_name="evidence",
                file_path="dummy/evidence.pdf",
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
        assert result == format_attachment(rows)

    def test_includes_archived_attachment_by_default(
        self, monkeypatch, sqlite_session, db_factory
    ) -> None:
        db_factory(
            attachment_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        monkeypatch.setattr(
            "compliance.services.attachments.formatting.format_attachment",
            lambda rows: rows[0]["Attachment"],
        )
        result = get_attachment_by_id(sqlite_session, 50)

        assert result is not None
        assert result.archived_at is not None

    def test_returns_none_when_archived_client_excluded(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(
            client_overrides={
                "archived_at": datetime.now(UTC),
                "archive_reason": "closed",
            },
        )

        result = get_attachment_by_id(sqlite_session, 50, include_archived=False)

        assert result is None

    def test_filters_optional_archive_links_in_outer_join_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        get_attachment_by_id(session, 50)

        statement_text = str(session.execute.call_args.args[0])

        assert "LEFT OUTER JOIN findings" in statement_text
        assert "findings.archived_at IS NULL" not in statement_text
        assert "LEFT OUTER JOIN rules" in statement_text
        assert "rules.archived_at IS NULL" not in statement_text
        assert "AND (findings.id IS NULL" not in statement_text
        assert "AND (rules.id IS NULL" not in statement_text

    def test_returns_none_when_archived_attachment_excluded(self) -> None:
        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = None

        result = get_attachment_by_id(session, 50, include_archived=False)

        stmt = session.execute.call_args.args[0]
        assert "attachments.archived_at IS NULL" in str(stmt)
        assert "sites.archived_at IS NULL" in str(stmt)
        assert "findings.archived_at IS NULL" in str(stmt)
        assert "rules.archived_at IS NULL" in str(stmt)
        assert result is None


class TestPostNewAttachment:
    def test_creates_metadata_with_null_file_path(
        self, sqlite_session, db_factory
    ) -> None:
        sqlite_session.add(
            User(
                id=10,
                email="inspector@example.com",
                hashed_password="hashed",  # noqa: S106
                full_name="Alice Inspector",
                role=Role.INSPECTOR,
                is_active=True,
                created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
            )
        )
        sqlite_session.commit()
        db_factory(certification_overrides={"inspector_id": 10})
        attachment = AttachmentCreate(
            file_name="pending_evidence",
            certification_id=42,
            description="Pending upload",
        )

        result = post_new_attachment(sqlite_session, attachment, user_id=10)
        persisted = sqlite_session.get(Attachment, result.id)

        assert result.file_path is None
        assert persisted.file_path is None
        assert result.uploaded_at is None

    def test_raises_when_certification_does_not_exist(self) -> None:
        attachment = AttachmentCreate(
            file_name="evidence",
            certification_id=100,
        )
        session = MagicMock()
        session.get.return_value = None

        with pytest.raises(
            AttachmentCertificationNotFoundError,
            match="Certification 100 does not exist",
        ):
            post_new_attachment(session, attachment, user_id=10)

        session.add.assert_not_called()

    def test_raises_when_certification_belongs_to_another_inspector(self) -> None:
        attachment = AttachmentCreate(
            file_name="evidence",
            certification_id=100,
        )
        session = MagicMock()
        session.get.return_value = SimpleNamespace(
            id=100,
            inspection_date=date(2026, 4, 1),
            inspector_id=11,
        )

        with pytest.raises(
            AttachmentPermissionError,
            match=re.escape(
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            ),
        ):
            post_new_attachment(session, attachment, user_id=10)

        session.get.assert_called_once_with(Certification, 100)
        session.add.assert_not_called()
        session.commit.assert_not_called()

    def test_raises_when_finding_does_not_exist(self) -> None:
        attachment = AttachmentCreate(
            file_name="evidence",
            certification_id=100,
            finding_ids=[7],
        )
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=100, inspection_date=date(2026, 4, 1), inspector_id=10),
            None,
        ]

        with pytest.raises(
            AttachmentFindingNotFoundError,
            match="Finding 7 does not exist",
        ):
            post_new_attachment(session, attachment, user_id=10)

        session.add.assert_not_called()

    def test_raises_when_finding_belongs_to_another_certification(self) -> None:
        attachment = AttachmentCreate(
            file_name="evidence",
            certification_id=100,
            finding_ids=[7],
        )
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=100, inspection_date=date(2026, 4, 1), inspector_id=10),
            SimpleNamespace(id=7, certification_id=200),
        ]

        with pytest.raises(
            AttachmentFindingCertificationMismatchError,
            match="Finding 7 does not belong to certification 100",
        ):
            post_new_attachment(session, attachment, user_id=10)

        session.add.assert_not_called()


class TestFormatNewAttachmentWithContext:
    def test_builds_attachment_output_with_certification_context(
        self, attachment_row_factory
    ) -> None:
        attachment = attachment_row_factory()
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

        result = format_attachment(rows)

        assert result == AttachmentWithContextOut(
            id=50,
            file_name="evidence",
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

        result = format_attachment(rows)

        assert result.id == 50
        assert [finding.finding_id for finding in result.finding_links] == [1, 2]
        assert [finding.rule_index for finding in result.finding_links] == [
            "7 CFR 205.201",
            "7 CFR 205.202",
        ]


class TestGetAttachmentDownload:
    def test_returns_download_name_and_file_path(
        self, tmp_path, sqlite_session, db_factory
    ) -> None:
        stored_file = tmp_path / "stored-file.pdf"
        stored_file.write_bytes(b"evidence")
        db_factory(
            attachment_overrides={
                "file_name": "inspection_report",
                "file_path": str(stored_file),
            },
        )

        file_name, file_path = get_attachment_download(sqlite_session, 50)

        assert file_name == "inspection_report.pdf"
        assert file_path == stored_file

    def test_returns_extension_only_when_file_name_is_empty(
        self, tmp_path, sqlite_session, db_factory
    ) -> None:
        stored_file = tmp_path / "stored-file.pdf"
        stored_file.write_bytes(b"evidence")
        db_factory(
            attachment_overrides={
                "file_name": "",
                "file_path": str(stored_file),
            },
        )

        file_name, file_path = get_attachment_download(sqlite_session, 50)

        assert file_name == ".pdf"
        assert file_path == stored_file

    def test_returns_extension_only_when_file_name_is_none(
        self, tmp_path, sqlite_session, db_factory
    ) -> None:
        stored_file = tmp_path / "stored-file.pdf"
        stored_file.write_bytes(b"evidence")
        db_factory(
            attachment_overrides={
                "file_name": None,
                "file_path": str(stored_file),
            },
        )

        file_name, file_path = get_attachment_download(sqlite_session, 50)

        assert file_name == ".pdf"
        assert file_path == stored_file

    def test_uses_db_id_and_sanitizes_download_file_name(
        self, tmp_path, sqlite_session, db_factory
    ) -> None:
        stored_file = tmp_path / "trusted-stored-name.pdf"
        stored_file.write_bytes(b"evidence")
        db_factory(
            attachment_overrides={
                "file_name": "../client/report",
                "file_path": str(stored_file),
            },
        )

        file_name, file_path = get_attachment_download(sqlite_session, 50)

        assert file_name == "report.pdf"
        assert file_path == stored_file

    def test_raises_file_error_when_file_path_is_none(
        self,
    ) -> None:
        session = MagicMock()
        session.get.return_value = SimpleNamespace(file_path=None)

        with pytest.raises(AttachmentFileError):
            get_attachment_download(session, 50)

    def test_raises_file_error_when_file_path_is_empty(
        self, sqlite_session, db_factory
    ) -> None:
        db_factory(attachment_overrides={"file_path": ""})

        with pytest.raises(AttachmentFileError):
            get_attachment_download(sqlite_session, 50)

    def test_raises_file_error_when_file_path_does_not_exist(
        self, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory(attachment_overrides={"file_path": str(tmp_path / "missing.pdf")})

        with pytest.raises(AttachmentFileError):
            get_attachment_download(sqlite_session, 50)

    def test_raises_not_found_error_when_attachment_does_not_exist(
        self, sqlite_session
    ) -> None:
        with pytest.raises(AttachmentNotFoundError):
            get_attachment_download(sqlite_session, 999)


class TestFileScanners:
    def test_noop_scanner_accepts_file_stream(self) -> None:
        file_stream = _upload_stream()

        NoOpFileScanner().scan(file_stream)

        assert file_stream.tell() == 0

    def test_noop_scanner_rejects_missing_file_stream(self) -> None:
        with pytest.raises(AttachmentScanError, match="No file to scan"):
            NoOpFileScanner().scan(None)

    def test_clamav_scanner_accepts_clean_result_and_rewinds_stream(
        self, monkeypatch
    ) -> None:
        class FakeClient:
            def instream(self, file_stream):
                assert file_stream.read() == b"%PDF-1.4\nbody"
                return {"stream": ("OK", None)}

        _install_fake_clamav_client(monkeypatch, FakeClient())
        scanner = ClamAVFileScanner(host="clamav", port=3310)
        file_stream = _upload_stream(b"%PDF-1.4\nbody")

        scanner.scan(file_stream)

        assert file_stream.tell() == 0

    @pytest.mark.parametrize(
        ("scan_result", "expected_error", "match"),
        [
            (
                {"stream": ("FOUND", "Eicar-Test-Signature")},
                AttachmentInfectedError,
                "Eicar-Test-Signature",
            ),
            (
                clamd.ResponseError("bad response"),
                AttachmentScanError,
                "invalid scan response",
            ),
            (
                clamd.ConnectionError("offline"),
                AttachmentScannerUnavailableError,
                "unavailable",
            ),
            (
                clamd.BufferTooLongError("too long"),
                AttachmentScanError,
                "stream-size limit",
            ),
            ({}, AttachmentScanError, "no scan result"),
            ({"stream": ("ERROR", "scan failed")}, AttachmentScanError, "scan failed"),
        ],
    )
    def test_clamav_scanner_maps_scan_failures(
        self, monkeypatch, scan_result, expected_error, match
    ) -> None:
        class FakeClient:
            def instream(self, file_stream):
                if isinstance(scan_result, Exception):
                    raise scan_result
                return scan_result

        _install_fake_clamav_client(monkeypatch, FakeClient())
        scanner = ClamAVFileScanner(host="clamav", port=3310)

        with pytest.raises(expected_error, match=match):
            scanner.scan(_upload_stream())


class TestPostAttachmentUpload:
    @pytest.fixture(autouse=True)
    def _stub_upload_dependencies(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "application/pdf",
        )
        self.scanner = MagicMock()
        monkeypatch.setattr(
            "compliance.services.attachments.files._build_file_scanner",
            lambda: self.scanner,
        )

    def test_upload_dir_is_independent_of_cwd(self, monkeypatch, tmp_path) -> None:
        upload_dir = _UPLOAD_DIR
        monkeypatch.chdir(tmp_path)

        assert upload_dir == _UPLOAD_DIR
        assert _UPLOAD_DIR.is_absolute()

    def test_stores_uploaded_file_and_updates_attachment_row(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        result = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=11,
            file_type="application/pdf",
            file_name="evidence.pdf",
            file_stream=_upload_stream(b"hello world"),
            user_id=None,
        )

        stored_path = tmp_path / Path(result.file_path).name
        assert result.id == 50
        assert result.file_path == str(stored_path)
        assert result.uploaded_at is not None
        assert stored_path.read_bytes() == b"hello world"
        self.scanner.scan.assert_called_once()

    def test_stores_allowed_image_upload(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "image/png",
        )

        result = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=8,
            file_type="image/png",
            file_name="evidence.png",
            file_stream=_upload_stream(b"\x89PNG\r\n\x1a\n"),
            user_id=None,
        )

        stored_path = Path(result.file_path)
        assert stored_path.parent == tmp_path
        assert stored_path.suffix == ".png"
        assert stored_path.read_bytes() == b"\x89PNG\r\n\x1a\n"
        self.scanner.scan.assert_called_once()

    def test_uses_uploaded_file_extension_for_stored_path(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        result = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=11,
            file_type="application/pdf",
            file_name="uploaded-name.pdf",
            file_stream=_upload_stream(b"hello world"),
            user_id=None,
        )

        assert Path(result.file_path).suffix == ".pdf"
        self.scanner.scan.assert_called_once()

    def test_duplicate_original_file_names_use_distinct_stored_paths(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        rows = db_factory()
        sqlite_session.add(
            Attachment(
                id=51,
                file_name="second evidence",
                certification_id=rows["certification"].id,
                description="Second inspection evidence",
            )
        )
        sqlite_session.commit()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        first = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=5,
            file_type="application/pdf",
            file_name="duplicate.pdf",
            file_stream=_upload_stream(b"first"),
            user_id=None,
        )
        second = post_attachment_upload(
            sqlite_session,
            attachment_id=51,
            file_size=6,
            file_type="application/pdf",
            file_name="duplicate.pdf",
            file_stream=_upload_stream(b"second"),
            user_id=None,
        )

        assert first.file_path != second.file_path
        assert Path(first.file_path).read_bytes() == b"first"
        assert Path(second.file_path).read_bytes() == b"second"

    def test_path_like_original_file_name_cannot_escape_storage(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        result = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=4,
            file_type="application/pdf",
            file_name="../../outside/evidence.pdf",
            file_stream=_upload_stream(b"data"),
            user_id=None,
        )

        stored_path = Path(result.file_path)
        assert stored_path.parent == tmp_path
        assert stored_path.name != "evidence.pdf"
        assert stored_path.read_bytes() == b"data"

    def test_preserves_attachment_display_file_name(
        self, monkeypatch, tmp_path, sqlite_session, db_factory
    ) -> None:
        db_factory(attachment_overrides={"file_name": "evidence"})
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        result = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=11,
            file_type="application/pdf",
            file_name="uploaded-name.pdf",
            file_stream=_upload_stream(b"hello world"),
            user_id=None,
        )

        assert result.file_name == "evidence"
        self.scanner.scan.assert_called_once()

    def test_scans_upload_before_fetching_attachment(self, monkeypatch) -> None:
        session = MagicMock()
        self.scanner.scan.side_effect = AttachmentScanError("scan failed")
        file_stream = _upload_stream(b"data")

        with pytest.raises(AttachmentScanError, match="scan failed"):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=4,
                file_type="application/pdf",
                file_name="evidence.pdf",
                file_stream=file_stream,
                user_id=10,
            )

        self.scanner.scan.assert_called_once_with(file_stream)
        session.get.assert_not_called()

    @pytest.mark.parametrize(
        ("scanner_error", "expected_error"),
        [
            (
                AttachmentInfectedError("Malware detected in uploaded file."),
                AttachmentInfectedError,
            ),
            (
                AttachmentScannerUnavailableError("ClamAV is unavailable."),
                AttachmentScannerUnavailableError,
            ),
        ],
    )
    def test_rejects_scanner_failures_before_writing_files(
        self, monkeypatch, tmp_path, scanner_error, expected_error
    ) -> None:
        session = MagicMock()
        self.scanner.scan.side_effect = scanner_error
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        with pytest.raises(expected_error):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=4,
                file_type="application/pdf",
                file_name="evidence.pdf",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        assert list(tmp_path.iterdir()) == []
        session.get.assert_not_called()

    def test_raises_unsupported_media_error_before_fetching_attachment_when_type_is_invalid(
        self,
    ) -> None:
        session = MagicMock()

        with pytest.raises(AttachmentUnsupportedMediaTypeError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=10,
                file_type="application/x-msdownload",
                file_name="evidence.exe",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_not_called()

    def test_raises_unsupported_media_error_before_fetching_attachment_when_content_type_is_invalid(
        self, monkeypatch
    ) -> None:
        session = MagicMock()
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "application/x-msdownload",
        )

        with pytest.raises(AttachmentUnsupportedMediaTypeError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=10,
                file_type="application/pdf",
                file_name="evidence.pdf",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_not_called()

    @pytest.mark.parametrize("file_name", [None, "", "   "])
    def test_raises_file_error_before_fetching_attachment_when_file_name_is_invalid(
        self, file_name
    ) -> None:
        session = MagicMock()

        with pytest.raises(AttachmentFileError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=10,
                file_type="application/pdf",
                file_name=file_name,
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_not_called()

    def test_raises_unsupported_media_error_before_fetching_attachment_when_extension_is_missing(
        self,
    ) -> None:
        session = MagicMock()

        with pytest.raises(AttachmentUnsupportedMediaTypeError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=10,
                file_type="application/pdf",
                file_name="evidence",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_not_called()

    def test_raises_unsupported_media_error_before_fetching_attachment_for_dangerous_inner_extension(
        self,
    ) -> None:
        session = MagicMock()

        with pytest.raises(AttachmentUnsupportedMediaTypeError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=10,
                file_type="application/pdf",
                file_name="evidence.exe.pdf",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_not_called()

    def test_raises_create_error_when_attachment_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        with pytest.raises(AttachmentCreateError):
            post_attachment_upload(
                session,
                attachment_id=999,
                file_size=10,
                file_type="application/pdf",
                file_name="evidence.pdf",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        session.get.assert_called_once_with(Attachment, 999)

    def test_deletes_written_file_when_database_commit_fails(
        self, monkeypatch, tmp_path
    ) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=50, certification_id=100),
            SimpleNamespace(inspector_id=10),
        ]
        session.commit.side_effect = IntegrityError(
            statement="SQL to create attachment",
            params=("attachment",),
            orig=Exception("UNIQUE constraint failed: attachment stuff"),
        )
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )

        with pytest.raises(AttachmentConflictError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=4,
                file_type="text/plain",
                file_name="evidence.txt",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        assert list(tmp_path.iterdir()) == []
        session.rollback.assert_called_once_with()

    def test_deletes_partial_file_and_rolls_back_when_upload_is_too_large(
        self, monkeypatch, tmp_path
    ) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(id=50, certification_id=100),
            SimpleNamespace(inspector_id=10),
        ]
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )
        monkeypatch.setattr("compliance.services.attachments.files._ALLOWED_SIZE", 3)

        with pytest.raises(AttachmentTooLargeError):
            post_attachment_upload(
                session,
                attachment_id=50,
                file_size=3,
                file_type="text/plain",
                file_name="evidence.txt",
                file_stream=_upload_stream(b"data"),
                user_id=10,
            )

        assert list(tmp_path.iterdir()) == []
        session.rollback.assert_called_once_with()
        session.commit.assert_not_called()


class TestCheckAttachmentStorage:
    def test_returns_true_when_upload_dir_accepts_writes(
        self, monkeypatch, tmp_path
    ) -> None:
        upload_dir = tmp_path / "attachments"
        upload_dir.mkdir()
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", upload_dir
        )

        assert check_attachment_storage() is True
        assert upload_dir.is_dir()
        assert list(upload_dir.iterdir()) == []

    def test_returns_false_when_upload_dir_does_not_exist(
        self, monkeypatch, tmp_path
    ) -> None:
        upload_dir = tmp_path / "attachments"
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", upload_dir
        )

        assert check_attachment_storage() is False

    def test_returns_false_when_upload_path_is_not_a_directory(
        self, monkeypatch, tmp_path
    ) -> None:
        upload_path = tmp_path / "attachments"
        upload_path.write_text("not a directory")
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", upload_path
        )

        assert check_attachment_storage() is False


class TestValidateFileSizeTypeAndExt:
    @pytest.fixture(autouse=True)
    def _stub_magic_mime(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "application/pdf",
        )

    def test_returns_true_for_allowed_size_type_extension_and_content(self) -> None:
        assert _validate_file_size_type_and_ext(
            10, "application/pdf", "evidence.pdf", _upload_stream()
        )

    def test_returns_false_for_zero_size(self) -> None:
        assert not _validate_file_size_type_and_ext(
            0, "application/pdf", "evidence.pdf", _upload_stream()
        )

    def test_returns_false_for_large_size(self) -> None:
        assert not _validate_file_size_type_and_ext(
            11,
            "application/pdf",
            "evidence.pdf",
            _upload_stream(),
            allowed_size=10,
        )

    def test_returns_false_for_missing_type(self) -> None:
        assert not _validate_file_size_type_and_ext(
            10, None, "evidence.pdf", _upload_stream()
        )

    def test_returns_false_for_bad_type(self) -> None:
        assert not _validate_file_size_type_and_ext(
            10, "application/x-msdownload", "evidence.pdf", _upload_stream()
        )

    def test_returns_false_for_bad_content_type(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "application/x-msdownload",
        )

        assert not _validate_file_size_type_and_ext(
            10, "application/pdf", "evidence.pdf", _upload_stream()
        )

    def test_passes_header_bytes_to_magic_and_rewinds_stream(self, monkeypatch) -> None:
        captured = {}

        def fake_from_buffer(header_bytes, mime):
            captured["header_bytes"] = header_bytes
            captured["mime"] = mime
            return "application/pdf"

        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            fake_from_buffer,
        )
        file_stream = _upload_stream(b"%PDF-1.4\nbody")

        assert _validate_file_size_type_and_ext(
            13, "application/pdf", "evidence.pdf", file_stream
        )
        assert captured == {"header_bytes": b"%PDF-1.4\nbody", "mime": True}
        assert file_stream.tell() == 0

    def test_returns_false_for_missing_extension(self) -> None:
        assert not _validate_file_size_type_and_ext(
            10, "application/pdf", "evidence", _upload_stream()
        )

    def test_returns_false_for_bad_extension(self) -> None:
        assert not _validate_file_size_type_and_ext(
            10, "application/pdf", "evidence.exe", _upload_stream()
        )

    @pytest.mark.parametrize("file_name", [None, "", "   "])
    def test_returns_false_for_missing_or_empty_file_name(self, file_name) -> None:
        assert not _validate_file_size_type_and_ext(
            10, "application/pdf", file_name, _upload_stream()
        )

    def test_returns_true_for_safe_multi_part_file_name(self) -> None:
        assert _validate_file_size_type_and_ext(
            10, "application/pdf", "inspection.report.pdf", _upload_stream()
        )

    @pytest.mark.parametrize(
        "file_name",
        [
            "evidence.exe.pdf",
            "evidence.sh.txt",
            "evidence.ps1.csv",
        ],
    )
    def test_returns_false_for_dangerous_inner_extension(self, file_name) -> None:
        assert not _validate_file_size_type_and_ext(
            10, "application/pdf", file_name, _upload_stream()
        )


class TestPostAttachmentArchivedById:
    def test_archives_attachment_and_returns_context(
        self, monkeypatch, assert_archived_record
    ) -> None:
        session = MagicMock()
        attachment = SimpleNamespace(
            certification_id=100,
            archived_at=None,
            archive_reason=None,
        )
        session.get.side_effect = [
            attachment,
            SimpleNamespace(inspector_id=10),
        ]
        expected = object()

        def fake_archive_record_by_id(
            session_arg, model, attachment_id, archive_request
        ):
            assert session_arg is session
            assert model is Attachment
            assert attachment_id == 50
            attachment.archived_at = datetime.now(UTC)
            attachment.archive_reason = archive_request.archive_reason
            return LifecycleResult(record=attachment, changed=True)

        def fake_get_attachment_by_id(session_arg, attachment_id, *, include_archived):
            assert session_arg is session
            assert attachment_id == 50
            assert include_archived is True
            return expected

        monkeypatch.setattr(
            "compliance.services.attachments.crud.archive_record_by_id",
            fake_archive_record_by_id,
        )
        monkeypatch.setattr(
            "compliance.services.attachments.crud.get_attachment_by_id",
            fake_get_attachment_by_id,
        )

        result = post_attachment_archived_by_id(
            session,
            50,
            archive_request=ArchiveRequest(archive_reason="old file"),
            user_id=10,
        )

        assert result is expected
        assert_archived_record(attachment, "old file")
        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_called_once_with()

    def test_archive_raises_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(certification_id=100),
            None,
        ]

        with pytest.raises(
            AttachmentCertificationNotFoundError,
            match=re.escape("Certification 100 does not exist."),
        ):
            post_attachment_archived_by_id(
                session,
                50,
                archive_request=ArchiveRequest(),
                user_id=10,
            )

        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_not_called()

    def test_archive_raises_when_certification_belongs_to_another_inspector(
        self,
    ) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(certification_id=100),
            SimpleNamespace(inspector_id=11),
        ]

        with pytest.raises(
            AttachmentPermissionError,
            match=re.escape(
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            ),
        ):
            post_attachment_archived_by_id(
                session,
                50,
                archive_request=ArchiveRequest(),
                user_id=10,
            )

        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_not_called()

    def test_returns_none_when_attachment_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_attachment_archived_by_id(
            session, 50, archive_request=ArchiveRequest(), user_id=10
        )

        assert result is None
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_not_called()


class TestPostAttachmentRestoredById:
    def test_restores_attachment_and_returns_context(
        self, monkeypatch, assert_restored_record
    ) -> None:
        session = MagicMock()
        attachment = SimpleNamespace(
            certification_id=100,
            archived_at=datetime(2026, 5, 8, 10, 0, tzinfo=UTC),
            archive_reason="old file",
        )
        session.get.side_effect = [
            attachment,
            SimpleNamespace(inspector_id=10),
        ]
        expected = object()

        def fake_restore_record_by_id(session_arg, model, attachment_id):
            assert session_arg is session
            assert model is Attachment
            assert attachment_id == 50
            attachment.archived_at = None
            attachment.archive_reason = None
            return LifecycleResult(record=attachment, changed=True)

        monkeypatch.setattr(
            "compliance.services.attachments.crud.restore_record_by_id",
            fake_restore_record_by_id,
        )
        monkeypatch.setattr(
            "compliance.services.attachments.crud.get_attachment_by_id",
            lambda session_arg, attachment_id, *, include_archived: expected,
        )

        result = post_attachment_restored_by_id(session, 50, user_id=10)

        assert result is expected
        assert_restored_record(attachment)
        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_called_once_with()

    def test_restore_raises_when_certification_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(certification_id=100),
            None,
        ]

        with pytest.raises(
            AttachmentCertificationNotFoundError,
            match=re.escape("Certification 100 does not exist."),
        ):
            post_attachment_restored_by_id(session, 50, user_id=10)

        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_not_called()

    def test_restore_raises_when_certification_belongs_to_another_inspector(
        self,
    ) -> None:
        session = MagicMock()
        session.get.side_effect = [
            SimpleNamespace(certification_id=100),
            SimpleNamespace(inspector_id=11),
        ]

        with pytest.raises(
            AttachmentPermissionError,
            match=re.escape(
                "Certification 100 is assigned to inspector 11.  "
                "You are logged in as inspector 10."
            ),
        ):
            post_attachment_restored_by_id(session, 50, user_id=10)

        assert session.get.call_args_list == [
            ((Attachment, 50),),
            ((Certification, 100),),
        ]
        session.commit.assert_not_called()

    def test_returns_none_when_attachment_does_not_exist(self) -> None:
        session = MagicMock()
        session.get.return_value = None

        result = post_attachment_restored_by_id(session, 50, user_id=10)

        assert result is None
        session.get.assert_called_once_with(Attachment, 50)
        session.commit.assert_not_called()


class TestPostAttachmentArchiveRestoreIntegration:
    def test_archive_then_restore_works(
        self, monkeypatch, sqlite_session, db_factory, assert_archive_restore_round_trip
    ) -> None:
        db_factory()
        monkeypatch.setattr(
            "compliance.services.attachments.crud.get_attachment_by_id",
            lambda session_arg, attachment_id, *, include_archived: session_arg.get(
                Attachment, attachment_id
            ),
        )

        assert_archive_restore_round_trip(
            sqlite_session,
            50,
            archive_fn=lambda session, attachment_id, *, archive_request: (
                post_attachment_archived_by_id(
                    session,
                    attachment_id,
                    archive_request=archive_request,
                    user_id=None,
                )
            ),
            restore_fn=lambda session, attachment_id: post_attachment_restored_by_id(
                session,
                attachment_id,
                user_id=None,
            ),
        )
