"""Authentication routes for OAuth2 password login and JWT creation."""

import logging
from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.auth.authentication import Token, authenticate_user, create_access_token
from compliance.db.models import AuditAction, AuditTargetType
from compliance.services.audit import record_audit_event
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_AUTH_SCHEME = "bearer"


@router.post("/token")
def post_auth_token_route(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Authenticate a user and return a bearer access token."""
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        _log_auth_failure(
            actor_email=form_data.username,
            reason="invalid_credentials",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        record_audit_event(
            session,
            action=AuditAction.LOGIN_FAILED,
            target_type=AuditTargetType.AUTH,
            actor_email=form_data.username,
            context={"reason": "invalid_credentials"},
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        _log_auth_failure(
            actor_user_id=user.id,
            actor_email=user.email,
            reason="inactive_user",
            status_code=status.HTTP_403_FORBIDDEN,
        )
        record_audit_event(
            session,
            action=AuditAction.LOGIN_FAILED,
            target_type=AuditTargetType.AUTH,
            actor_user_id=user.id,
            actor_email=user.email,
            context={"reason": "inactive_user"},
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(user.email)
    record_audit_event(
        session,
        action=AuditAction.LOGIN_SUCCESS,
        target_type=AuditTargetType.AUTH,
        actor_user_id=user.id,
        actor_email=user.email,
    )
    session.commit()

    return Token(access_token=access_token, token_type=_AUTH_SCHEME)


def _log_auth_failure(
    *,
    actor_email: str,
    reason: str,
    status_code: int,
    actor_user_id: int | None = None,
) -> None:
    """Log safe, queryable context for a failed authentication attempt."""
    logger.warning(
        "Authentication failed.",
        extra={
            "event": "auth_failed",
            "actor_user_id": actor_user_id,
            "actor_email": actor_email,
            "reason": reason,
            "status_code": status_code,
        },
    )
