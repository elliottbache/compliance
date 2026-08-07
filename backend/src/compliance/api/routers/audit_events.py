"""Admin audit event routes."""

from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import AuditEventOut
from compliance.auth.authorization import require_role
from compliance.db.models import AuditAction, AuditTargetType, Role
from compliance.services.audit import get_audit_events
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime

router = APIRouter(prefix="/audit-events", tags=["audit-events"])


@router.get("")
def get_audit_events_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    actor_user_id: Annotated[int | None, Query(gt=0)] = None,
    actor_email: Annotated[str | None, Query(max_length=80)] = None,
    action: Annotated[AuditAction | None, Query()] = None,
    target_type: Annotated[AuditTargetType | None, Query()] = None,
    target_id: Annotated[str | None, Query(max_length=80)] = None,
    created_from: Annotated[AwareDatetime | None, Query()] = None,
    created_to: Annotated[AwareDatetime | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventOut]:
    """Return audit events with optional filters."""
    if (
        created_from is not None
        and created_to is not None
        and created_from > created_to
    ):
        raise HTTPException(
            status_code=422,
            detail="created_from must be before or equal to created_to.",
        )

    audit_events = get_audit_events(
        session,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )

    return [AuditEventOut.model_validate(audit_event) for audit_event in audit_events]
