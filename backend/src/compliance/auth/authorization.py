from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from compliance.api.deps import SessionDep
from compliance.auth.authentication import (
    _get_user_in_db,
    _to_user_out,
    decode_access_token,
    oauth2_scheme,
)
from compliance.db.models import Role
from compliance.services.schemas import UserOut

_ROLE_RANK = {
    Role.VIEWER: 0,
    Role.REVIEWER: 1,
    Role.INSPECTOR: 2,
    Role.ADMIN: 3,
}


def get_current_user(
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserOut:
    """Return public user details for the bearer token subject."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_data = decode_access_token(token)
    except HTTPException as err:
        raise credentials_exception from err

    user = _get_user_in_db(session, token_data.email)
    if user is None:
        raise credentials_exception

    return _to_user_out(user)


def get_active_user(
    current_user: Annotated[UserOut, Depends(get_current_user)],
) -> UserOut:
    """Return the current user when the account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user


def require_role(minimum_role: Role) -> Callable[..., UserOut]:
    """Return a dependency that requires the given role or a higher role."""

    def dependency(
        user: UserOut = Depends(get_current_user),  # noqa: B008
    ) -> UserOut:
        if _ROLE_RANK[user.role] < _ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    return dependency
