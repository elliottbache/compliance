from datetime import UTC, datetime

import pytest
from compliance.db.models import (
    Attachment,
    AuditAction,
    AuditEvent,
    AuditTargetType,
    Certification,
    Certifier,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from sqlalchemy import CheckConstraint


def test_finding_attachments_primary_key_excludes_certification_id() -> None:
    pk_columns = {
        column.name for column in FindingAttachment.__table__.primary_key.columns
    }

    assert pk_columns == {"finding_id", "attachment_id"}


def test_audit_event_actor_user_id_references_users() -> None:
    foreign_keys = AuditEvent.__table__.columns["actor_user_id"].foreign_keys
    targets = {foreign_key.target_fullname for foreign_key in foreign_keys}

    assert targets == {"users.id"}


def test_audit_event_context_uses_json_type() -> None:
    context_column = AuditEvent.__table__.columns["context"]

    assert context_column.type.python_type is dict


def test_audit_event_created_at_column_is_timezone_aware() -> None:
    created_at_column = AuditEvent.__table__.columns["created_at"]

    assert created_at_column.type.timezone is True


def test_audit_action_values_are_defined() -> None:
    assert {action.value for action in AuditAction} == {
        "finding.created",
        "finding.updated",
        "finding.archived",
        "finding.restored",
        "attachment.uploaded",
        "attachment.downloaded",
        "certification.created",
        "certification.updated",
        "certification.archived",
        "certification.restored",
        "record.archived",
        "record.restored",
        "ai.analysis_requested",
        "ai.report_generated",
        "user.created",
        "user.disabled",
        "login.success",
        "login.failed",
        "authorization.failed",
    }


def test_audit_target_type_values_are_defined() -> None:
    assert {target_type.value for target_type in AuditTargetType} == {
        "finding",
        "attachment",
        "certification",
        "record",
        "ai",
        "user",
        "auth",
    }


def test_audit_event_action_and_target_type_check_constraints_exist() -> None:
    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in AuditEvent.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_audit_events_action_check" in check_constraints
    assert "ck_audit_events_target_type_check" in check_constraints
    assert "finding.created" in check_constraints["ck_audit_events_action_check"]
    assert "authorization.failed" in check_constraints["ck_audit_events_action_check"]
    assert "certification" in check_constraints["ck_audit_events_target_type_check"]
    assert "auth" in check_constraints["ck_audit_events_target_type_check"]


def test_audit_event_filter_indexes_exist() -> None:
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in AuditEvent.__table__.indexes
    }

    assert indexes["ix_audit_events_actor_user_id"] == ("actor_user_id",)
    assert indexes["ix_audit_events_actor_email"] == ("actor_email",)
    assert indexes["ix_audit_events_action"] == ("action",)
    assert indexes["ix_audit_events_created_at"] == ("created_at",)
    assert indexes["ix_audit_events_target_type_target_id"] == (
        "target_type",
        "target_id",
    )


@pytest.mark.parametrize(
    "model",
    [
        Attachment,
        Certification,
        Certifier,
        Client,
        Finding,
        Regulation,
        Rule,
        Site,
    ],
)
def test_archived_at_columns_are_timezone_aware(model) -> None:
    archived_at_column = model.__table__.columns["archived_at"]

    assert archived_at_column.type.timezone is True


class TestSqliteDatetimePolicy:
    def test_loaded_archived_at_is_normalized_to_utc(self, sqlite_session) -> None:
        archived_at = datetime(2026, 5, 16, 8, 0, tzinfo=UTC)
        client = Client(
            nif="A1234567B",
            company_name="Acme Corp",
            contact_name="John Doe",
            email=None,
            telephone=None,
            archived_at=archived_at,
            archive_reason="duplicate",
        )
        sqlite_session.add(client)
        sqlite_session.commit()
        sqlite_session.expunge_all()

        result = sqlite_session.get(Client, "A1234567B")

        assert result.archived_at.tzinfo is UTC

    def test_refreshed_archived_at_is_normalized_to_utc(self, sqlite_session) -> None:
        client = Client(
            nif="A1234567B",
            company_name="Acme Corp",
            contact_name="John Doe",
            email=None,
            telephone=None,
            archived_at=datetime(2026, 5, 16, 8, 0, tzinfo=UTC),
            archive_reason="duplicate",
        )
        sqlite_session.add(client)
        sqlite_session.commit()

        result = sqlite_session.get(Client, "A1234567B")

        assert result.archived_at.tzinfo is UTC
