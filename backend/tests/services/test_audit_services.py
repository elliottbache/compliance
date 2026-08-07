from datetime import UTC
from unittest.mock import MagicMock

import pytest
from compliance.db.models import AuditAction, AuditEvent, AuditTargetType
from compliance.services.audit import AuditContextError, record_audit_event


class TestRecordAuditEvent:
    def test_creates_and_flushes_audit_event(self, sqlite_session) -> None:
        audit_event = record_audit_event(
            sqlite_session,
            action=AuditAction.FINDING_CREATED,
            target_type=AuditTargetType.FINDING,
            target_id="42",
            actor_user_id=None,
            actor_email="alice@example.com",
            context={"finding_id": 42},
        )

        assert audit_event.id is not None
        assert audit_event.action == AuditAction.FINDING_CREATED
        assert audit_event.target_type == AuditTargetType.FINDING
        assert audit_event.target_id == "42"
        assert audit_event.actor_user_id is None
        assert audit_event.actor_email == "alice@example.com"
        assert audit_event.context == {"finding_id": 42}
        assert audit_event.created_at.tzinfo is UTC

        persisted = sqlite_session.get(AuditEvent, audit_event.id)
        assert persisted is audit_event

    def test_defaults_context_to_empty_dict(self, sqlite_session) -> None:
        audit_event = record_audit_event(
            sqlite_session,
            action=AuditAction.LOGIN_FAILED,
            target_type=AuditTargetType.AUTH,
        )

        assert audit_event.context == {}

    def test_copies_context_mapping(self, sqlite_session) -> None:
        context = {"site_id": 12}

        audit_event = record_audit_event(
            sqlite_session,
            action=AuditAction.AI_ANALYSIS_REQUESTED,
            target_type=AuditTargetType.AI,
            target_id="12",
            context=context,
        )
        context["site_id"] = 99

        assert audit_event.context == {"site_id": 12}
        assert audit_event.context is not context

    def test_converts_integer_target_id_to_string(self, sqlite_session) -> None:
        audit_event = record_audit_event(
            sqlite_session,
            action=AuditAction.CERTIFICATION_ARCHIVED,
            target_type=AuditTargetType.CERTIFICATION,
            target_id=100,
        )

        assert audit_event.target_id == "100"

    def test_accepts_missing_actor_fields(self, sqlite_session) -> None:
        audit_event = record_audit_event(
            sqlite_session,
            action=AuditAction.AUTHORIZATION_FAILED,
            target_type=AuditTargetType.AUTH,
            context={"path": "/findings"},
        )

        assert audit_event.actor_user_id is None
        assert audit_event.actor_email is None

    def test_raises_context_error_for_non_json_serializable_context(self) -> None:
        session = MagicMock()

        with pytest.raises(AuditContextError, match="JSON serializable"):
            record_audit_event(
                session,
                action=AuditAction.RECORD_ARCHIVED,
                target_type=AuditTargetType.RECORD,
                context={"bad": object()},
            )

        session.add.assert_not_called()
        session.flush.assert_not_called()

    def test_does_not_commit_or_roll_back(self) -> None:
        session = MagicMock()

        audit_event = record_audit_event(
            session,
            action=AuditAction.ATTACHMENT_DOWNLOADED,
            target_type=AuditTargetType.ATTACHMENT,
            target_id=7,
            actor_user_id=10,
            actor_email="alice@example.com",
        )

        session.add.assert_called_once_with(audit_event)
        session.flush.assert_called_once_with()
        session.commit.assert_not_called()
        session.rollback.assert_not_called()
