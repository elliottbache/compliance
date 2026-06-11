from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance.auth.passwords import hash_password, verify_password
from compliance.db.models import User
from compliance.services.schemas import UserInDB

_DUMMY_HASH = hash_password("dummy_password")


def get_user(session: Session, email: EmailStr) -> UserInDB | None:
    """Return a user by email, or None when no matching user exists."""
    stmt = select(User).where(User.email == email)
    user = session.execute(stmt).scalars().first()

    return user if user is None else UserInDB.model_validate(user)


def authenticate_user(
    session: Session, email: EmailStr, password: str
) -> UserInDB | None:
    """Return the user when supplied credentials are valid."""
    user = get_user(session, email)
    if not user:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None

    return user
