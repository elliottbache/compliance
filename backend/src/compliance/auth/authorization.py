from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from jwt.exceptions import InvalidTokenError

from compliance.api.deps import SessionDep
from compliance.auth.authentication import (
    TokenData,
    _get_token_settings,
    get_user,
    oauth2_scheme,
)
from compliance.db.models import Role
from compliance.services.schemas import UserInDB


def get_current_user(
    session: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> UserInDB:
    secret_key, algorithm, _ = _get_token_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(email=username)
    except InvalidTokenError as err:
        raise credentials_exception from err

    user = get_user(session, token_data.email)
    if user is None:
        raise credentials_exception

    return user


def get_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserInDB:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return current_user


def require_role(allowed_role: Role) -> Callable[..., UserInDB]:
    def dependency(
        user: UserInDB = Depends(get_current_user),  # noqa: B008
    ) -> UserInDB:
        if user.role != allowed_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    return dependency
