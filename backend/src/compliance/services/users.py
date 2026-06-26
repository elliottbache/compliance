"""User service functions for listing and password-backed user creation."""

from dataclasses import dataclass
from datetime import UTC, datetime

from compliance.auth.authentication import _hash_password
from compliance.db.models import (
    Role,
    User,
)
from compliance.services.lifecycle import (
    get_constraint_name,
)
from compliance.services.schemas import (
    UserCreate,
    UserOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class UserConflictError(Exception):
    """Raised when a user cannot be created because of existing data."""


class UserEmailConflictError(UserConflictError):
    """Raised when a user email already exists."""


@dataclass(frozen=True)
class FirstAdminBootstrapResult:
    """Result returned by the first-admin bootstrap flow."""

    created: bool
    user: UserOut | None


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


def bootstrap_first_admin(
    session: Session, *, full_name: str, email: str, password: str
) -> FirstAdminBootstrapResult:
    """Create the first active admin user when no active admin exists.

    Args:
        session: Database session used to check and create users.
        full_name: Display name for the bootstrap admin user.
        email: Login email for the bootstrap admin user.
        password: Plaintext password to hash before storage.

    Returns:
        A bootstrap result indicating whether a new admin was created. If an
        active admin already exists, no user is created and ``user`` is ``None``.

    Raises:
        UserEmailConflictError: If no active admin exists but the email is
            already used by another user.
        UserConflictError: If another integrity conflict prevents creation.
    """
    stmt = select(User).where(User.role == Role.ADMIN, User.is_active.is_(True))
    existing_admin = session.execute(stmt).scalars().first()
    if existing_admin is not None:
        return FirstAdminBootstrapResult(created=False, user=None)

    user = post_new_user(
        session,
        UserCreate(
            full_name=full_name,
            email=email,
            password=password,
            role=Role.ADMIN,
            is_active=True,
        ),
    )

    return FirstAdminBootstrapResult(created=True, user=user)
