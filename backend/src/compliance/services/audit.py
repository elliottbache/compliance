"""Audit event service helpers."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from compliance.db.models import AuditAction, AuditEvent, AuditTargetType
from sqlalchemy import select
from sqlalchemy.orm import Session


class AuditContextError(Exception):
    """Raised when audit metadata cannot be stored as JSON."""


def get_audit_events(
    session: Session,
    *,
    actor_user_id: int | None,
    actor_email: str | None,
    action: AuditAction | None,
    target_type: AuditTargetType | None,
    target_id: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int | None,
    offset: int,
) -> list[AuditEvent]:
    """Retrieve audit events with optional filters, newest first.

    Args:
        session: Database session used to query audit events.
        actor_user_id: Optional actor user ID filter.
        actor_email: Optional actor email snapshot filter.
        action: Optional audit action filter.
        target_type: Optional target category filter.
        target_id: Optional target identifier filter.
        created_from: Optional inclusive lower created-at bound.
        created_to: Optional inclusive upper created-at bound.
        limit: Maximum number of audit events to return. If ``None``, all
            matching audit events are returned.
        offset: Number of matching audit events to skip.

    Returns:
        Matching audit event rows ordered by newest timestamp and ID.
    """
    stmt = select(AuditEvent)

    if actor_user_id is not None:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    if actor_email is not None:
        stmt = stmt.where(AuditEvent.actor_email == actor_email)
    if action is not None:
        stmt = stmt.where(AuditEvent.action == action)
    if target_type is not None:
        stmt = stmt.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    if created_from is not None:
        stmt = stmt.where(AuditEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditEvent.created_at <= created_to)

    stmt = stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
    stmt = stmt.limit(limit).offset(offset)

    return list(session.execute(stmt).scalars().all())


def record_audit_event(
    session: Session,
    *,
    action: AuditAction,
    target_type: AuditTargetType,
    target_id: str | int | None = None,
    actor_user_id: int | None = None,
    actor_email: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> AuditEvent:
    """Create an audit event in the current transaction.

    Args:
        session: Database session used to add and flush the audit event.
        action: Controlled audit action name.
        target_type: Controlled target category for the affected record or flow.
        target_id: Optional target identifier, stored as a string when present.
        actor_user_id: Optional authenticated user ID.
        actor_email: Optional actor email snapshot.
        context: Optional safe JSON-shaped metadata.

    Returns:
        The flushed audit event.

    Raises:
        AuditContextError: If ``context`` cannot be serialized as JSON.
    """
    context_dict = dict(context or {})
    try:
        json.dumps(context_dict)
    except (TypeError, ValueError) as exc:
        raise AuditContextError(
            "Audit event context must be JSON serializable."
        ) from exc

    audit_event = AuditEvent(
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        created_at=datetime.now(UTC),
        context=context_dict,
    )

    session.add(audit_event)
    session.flush()

    return audit_event
