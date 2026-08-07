from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from compliance.db.models import AuditAction, AuditEvent, Role, User
from compliance.services.attachments import (
    get_attachment_download,
    post_attachment_upload,
)
from compliance.services.certifications import post_certification_archived_by_id
from compliance.services.clients import post_client_archived_by_nif
from compliance.services.findings import post_new_finding
from compliance.services.schemas import ArchiveRequest, FindingCreate, UserCreate
from compliance.services.users import post_new_user
from sqlalchemy import select


def _actor() -> User:
    return User(
        id=10,
        email="inspector@example.com",
        hashed_password="hashed",  # noqa: S106
        full_name="Alice Inspector",
        role=Role.INSPECTOR,
        is_active=True,
        created_at=datetime(2026, 6, 13, 10, 0, tzinfo=UTC),
    )


def _audit_events(session) -> list[AuditEvent]:
    return list(session.execute(select(AuditEvent)).scalars().all())


class TestAuditedServiceActions:
    def test_records_user_created_when_actor_is_provided(self, sqlite_session) -> None:
        actor = _actor()
        sqlite_session.add(actor)
        sqlite_session.commit()

        created_user = post_new_user(
            sqlite_session,
            UserCreate(
                full_name="Bob Reviewer",
                email="bob@example.com",
                password="test-password",  # noqa: S106
                role=Role.REVIEWER,
            ),
            actor=actor,
        )

        event = _audit_events(sqlite_session)[0]
        assert event.action == AuditAction.USER_CREATED
        assert event.actor_user_id == actor.id
        assert event.actor_email == actor.email
        assert event.target_id == str(created_user.id)
        assert event.context == {
            "user_id": created_user.id,
            "email": "bob@example.com",
            "role": Role.REVIEWER.value,
        }

    def test_records_finding_created_when_actor_is_provided(
        self, sqlite_session, db_factory, monkeypatch
    ) -> None:
        actor = _actor()
        sqlite_session.add(actor)
        sqlite_session.commit()
        db_factory(certification_overrides={"inspector_id": actor.id})
        monkeypatch.setattr(
            "compliance.services.findings._format_findings",
            lambda rows: ["created-finding"],
        )

        post_new_finding(
            sqlite_session,
            FindingCreate(
                certification_id=42,
                rule_id=5,
                finding="Missing document",
                attachment_ids=[50],
            ),
            actor,
        )

        event = _audit_events(sqlite_session)[0]
        assert event.action == AuditAction.FINDING_CREATED
        assert event.actor_email == actor.email
        assert event.context["certification_id"] == 42
        assert event.context["rule_id"] == 5
        assert event.context["attachment_ids"] == [50]

    def test_records_certification_archived_when_actor_is_provided(
        self, sqlite_session, db_factory
    ) -> None:
        actor = _actor()
        sqlite_session.add(actor)
        sqlite_session.commit()
        db_factory()

        post_certification_archived_by_id(
            sqlite_session,
            42,
            archive_request=ArchiveRequest(archive_reason="duplicate"),
            actor=actor,
        )

        event = _audit_events(sqlite_session)[0]
        assert event.action == AuditAction.CERTIFICATION_ARCHIVED
        assert event.target_id == "42"
        assert event.context["archive_reason"] == "duplicate"

    def test_records_attachment_upload_and_download_when_actor_is_provided(
        self, sqlite_session, db_factory, monkeypatch, tmp_path
    ) -> None:
        actor = _actor()
        sqlite_session.add(actor)
        sqlite_session.commit()
        db_factory(certification_overrides={"inspector_id": actor.id})
        monkeypatch.setattr(
            "compliance.services.attachments.files._UPLOAD_DIR", tmp_path
        )
        monkeypatch.setattr(
            "compliance.services.attachments.files.magic.from_buffer",
            lambda header_bytes, mime: "application/pdf",
        )
        monkeypatch.setattr(
            "compliance.services.attachments.files._build_file_scanner",
            lambda: type("Scanner", (), {"scan": lambda self, file_stream: None})(),
        )

        uploaded = post_attachment_upload(
            sqlite_session,
            attachment_id=50,
            file_size=11,
            file_type="application/pdf",
            file_name="evidence.pdf",
            file_stream=BytesIO(b"hello world"),
            actor=actor,
        )
        file_name, file_path = get_attachment_download(
            sqlite_session, uploaded.id, actor=actor
        )

        events = _audit_events(sqlite_session)
        assert [event.action for event in events] == [
            AuditAction.ATTACHMENT_UPLOADED,
            AuditAction.ATTACHMENT_DOWNLOADED,
        ]
        assert events[0].context["file_size"] == 11
        assert file_name == "evidence.pdf"
        assert file_path == Path(uploaded.file_path)

    def test_records_generic_record_archived_when_actor_is_provided(
        self, sqlite_session, db_factory
    ) -> None:
        actor = _actor()
        sqlite_session.add(actor)
        sqlite_session.commit()
        db_factory()

        post_client_archived_by_nif(
            sqlite_session,
            "A1234567B",
            archive_request=ArchiveRequest(archive_reason="closed"),
            actor=actor,
        )

        event = _audit_events(sqlite_session)[0]
        assert event.action == AuditAction.RECORD_ARCHIVED
        assert event.target_id == "A1234567B"
        assert event.context == {
            "record_type": "client",
            "nif": "A1234567B",
            "archive_reason": "closed",
        }
