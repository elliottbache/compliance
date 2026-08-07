"""Authentication routes for OAuth2 password login and JWT creation."""

from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.auth.authentication import Token, authenticate_user, create_access_token
from compliance.db.models import AuditAction, AuditTargetType
from compliance.services.audit import record_audit_event
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])
_AUTH_SCHEME = "bearer"


@router.post("/token")
def post_auth_token_route(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """Authenticate a user and return a bearer access token."""
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
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
