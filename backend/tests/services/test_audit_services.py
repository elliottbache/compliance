from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from compliance.db.models import AuditAction, AuditEvent, AuditTargetType, Role, User
from compliance.services.audit import (
    AuditContextError,
    get_audit_events,
    record_audit_event,
)


def _audit_event(**overrides) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=None,
        actor_email="alice@example.com",
        action=AuditAction.FINDING_CREATED,
        target_type=AuditTargetType.FINDING,
        target_id="42",
        created_at=datetime(2026, 8, 7, 10, 0, tzinfo=UTC),
        context={"finding_id": 42},
    )
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


def _user(**overrides) -> User:
    user = User(
        id=10,
        email="alice@example.com",
        hashed_password="dummy_hash",  # noqa: S106
        full_name="Alice Inspector",
        role=Role.ADMIN,
        is_active=True,
        created_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
    )
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


def _get_audit_events(sqlite_session, **overrides) -> list[AuditEvent]:
    filters = {
        "actor_user_id": None,
        "actor_email": None,
        "action": None,
        "target_type": None,
        "target_id": None,
        "created_from": None,
        "created_to": None,
        "limit": None,
        "offset": 0,
    }
    filters.update(overrides)
    return get_audit_events(sqlite_session, **filters)


class TestGetAuditEvents:
    def test_returns_events_newest_first_with_id_tie_breaker(
        self, sqlite_session
    ) -> None:
        timestamp = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        older = _audit_event(created_at=timestamp - timedelta(hours=1), target_id="1")
        first_same_time = _audit_event(created_at=timestamp, target_id="2")
        second_same_time = _audit_event(created_at=timestamp, target_id="3")
        sqlite_session.add_all([older, first_same_time, second_same_time])
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session)

        assert [event.target_id for event in result] == ["3", "2", "1"]

    def test_filters_by_actor_user_id(self, sqlite_session) -> None:
        user = _user()
        sqlite_session.add(user)
        sqlite_session.flush()
        sqlite_session.add_all(
            [
                _audit_event(actor_user_id=10, target_id="match"),
                _audit_event(actor_user_id=None, target_id="skip"),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, actor_user_id=10)

        assert [event.target_id for event in result] == ["match"]

    def test_filters_by_actor_email(self, sqlite_session) -> None:
        sqlite_session.add_all(
            [
                _audit_event(actor_email="alice@example.com", target_id="match"),
                _audit_event(actor_email="bob@example.com", target_id="skip"),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, actor_email="alice@example.com")

        assert [event.target_id for event in result] == ["match"]

    def test_filters_by_action(self, sqlite_session) -> None:
        sqlite_session.add_all(
            [
                _audit_event(action=AuditAction.LOGIN_FAILED, target_id="match"),
                _audit_event(action=AuditAction.LOGIN_SUCCESS, target_id="skip"),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, action=AuditAction.LOGIN_FAILED)

        assert [event.target_id for event in result] == ["match"]

    def test_filters_by_target_type(self, sqlite_session) -> None:
        sqlite_session.add_all(
            [
                _audit_event(target_type=AuditTargetType.AUTH, target_id="match"),
                _audit_event(target_type=AuditTargetType.FINDING, target_id="skip"),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, target_type=AuditTargetType.AUTH)

        assert [event.target_id for event in result] == ["match"]

    def test_filters_by_target_id(self, sqlite_session) -> None:
        sqlite_session.add_all(
            [
                _audit_event(target_id="match"),
                _audit_event(target_id="skip"),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, target_id="match")

        assert [event.target_id for event in result] == ["match"]

    def test_applies_inclusive_created_at_bounds(self, sqlite_session) -> None:
        created_from = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        created_to = datetime(2026, 8, 7, 11, 0, tzinfo=UTC)
        sqlite_session.add_all(
            [
                _audit_event(
                    created_at=created_from - timedelta(seconds=1),
                    target_id="too-early",
                ),
                _audit_event(created_at=created_from, target_id="from-bound"),
                _audit_event(created_at=created_to, target_id="to-bound"),
                _audit_event(
                    created_at=created_to + timedelta(seconds=1),
                    target_id="too-late",
                ),
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(
            sqlite_session,
            created_from=created_from,
            created_to=created_to,
        )

        assert [event.target_id for event in result] == ["to-bound", "from-bound"]

    def test_applies_limit_and_offset(self, sqlite_session) -> None:
        sqlite_session.add_all(
            [
                _audit_event(created_at=datetime(2026, 8, 7, hour, tzinfo=UTC))
                for hour in [8, 9, 10]
            ]
        )
        sqlite_session.commit()

        result = _get_audit_events(sqlite_session, limit=1, offset=1)

        assert len(result) == 1
        assert result[0].created_at.hour == 9


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
