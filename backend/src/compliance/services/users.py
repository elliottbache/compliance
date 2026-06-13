from datetime import UTC, datetime

from compliance.api.schemas import (
    UserCreate,
    UserOut,
)
from compliance.auth.authentication import _hash_password
from compliance.db.models import (
    User,
)
from compliance.services.lifecycle import (
    get_constraint_name,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class UserConflictError(Exception):
    """Raised when a user cannot be created because of existing data."""


class UserEmailConflictError(UserConflictError):
    """Raised when a user email already exists."""


def get_users(
    session: Session, *, limit: int | None, offset: int, include_inactive: bool = False
) -> list[User]:
    """Retrieve users ordered by full name and ID.

    Args:
        session: Database session used to execute the user query.
        limit: Maximum number of users to return. If ``None``, all
            users are returned.
        offset: Number of users to skip before returning results.
        include_inactive: When true, include archived users in addition to active users.

    Returns:
        User ORM objects, or an empty list if no users exist.
    """
    stmt = select(User)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))

    stmt = stmt.order_by(User.full_name, User.id).limit(limit).offset(offset)
    return list(session.execute(stmt).scalars().all())


def post_new_user(session: Session, user: UserCreate) -> UserOut:
    """Persist a new user record.

    Args:
        session: Database session used to add and commit the user.
        user: User data validated by the API layer.

    Returns:
        The created User ORM object.

    Raises:
        UserEmailConflictError: If the email already exists.
        UserConflictError: If another integrity conflict prevents the
            insert.
    """
    user_dict = user.model_dump(exclude={"password"})
    user_dict["created_at"] = datetime.now(UTC)
    user_dict["hashed_password"] = _hash_password(user.password)
    new_user = User(**user_dict)

    try:
        session.add(new_user)
        session.commit()

    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "uq_users_email":
            raise UserEmailConflictError(
                f"User with email {user.email} already exists."
            ) from exc

        raise UserConflictError(
            "User was not added because of a data conflict."
        ) from exc

    return UserOut.model_validate(new_user)
