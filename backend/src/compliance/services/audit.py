"""Audit event service helpers."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from compliance.db.models import AuditAction, AuditEvent, AuditTargetType
from sqlalchemy.orm import Session


class AuditContextError(Exception):
    """Raised when audit metadata cannot be stored as JSON."""


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
