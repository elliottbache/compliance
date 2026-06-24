"""User administration routes for listing and creating users."""

from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    UserCreate,
    UserOut,
)
from compliance.auth.authentication import oauth2_scheme
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.users import (
    UserConflictError,
    UserEmailConflictError,
    get_users,
    post_new_user,
)
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def get_users_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    token: Annotated[str, Depends(oauth2_scheme)],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[UserOut]:
    """Return users with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of users to return.
        offset: Number of users to skip before returning results.
        include_inactive: When true, include inactive users.

    Returns:
        User records serialized with the public API response schema.
    """
    users = get_users(
        session, limit=limit, offset=offset, include_inactive=include_inactive
    )
    return [UserOut.model_validate(user) for user in users]


@router.post("", status_code=201)
def post_new_user_route(
    session: SessionDep,
    user: UserCreate,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
) -> UserOut:
    """Create a new user record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        user: User details supplied in the request body.

    Returns:
        Created user details serialized with the public API response
        schema.

    Raises:
        HTTPException: If the user cannot be created, such as when it
            conflicts with an existing record.
    """
    try:
        new_user = post_new_user(session, user)

    except UserEmailConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=str(err),
        ) from err

    except UserConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err

    return UserOut.model_validate(new_user)
