from datetime import UTC, datetime, timedelta
from os import getenv

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from compliance._helpers import ROOT_DIR
from compliance.db.models import User
from compliance.services.schemas import UserInDB

_DEFAULT_EXPIRE_MINUTES = 30
_DOTENV_PATH = ROOT_DIR / "backend" / ".env"


class Token(BaseModel):
    """Represents a bearer token response returned by the auth endpoint."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Represents the authenticated user identity extracted from a JWT."""

    email: EmailStr


password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def authenticate_user(
    session: Session, email: EmailStr, password: str
) -> UserInDB | None:
    """Return the user when supplied credentials are valid."""
    user = get_user(session, email)
    dummy_hash = _hash_password("dummy_password")
    if not user:
        _verify_password(password, dummy_hash)
        return None
    if not _verify_password(password, user.hashed_password):
        return None

    return user


def get_user(session: Session, email: EmailStr) -> UserInDB | None:
    """Return a user by email, or None when no matching user exists."""
    stmt = select(User).where(User.email == email)
    user = session.execute(stmt).scalars().first()

    return user if user is None else UserInDB.model_validate(user)


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored password hash."""
    return password_hash.verify(plain_password, hashed_password)


def _hash_password(password: str) -> str:
    """Hash a plaintext password using the configured password hasher."""
    return password_hash.hash(password)


def _get_token_settings() -> tuple[str, str, int]:
    """Load token configuration from environment variables and the backend .env."""
    load_dotenv(dotenv_path=_DOTENV_PATH, override=False)

    secret_key = getenv("SECRET_KEY")
    algorithm = getenv("ALGORITHM", "HS256")
    expire_minutes = getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(_DEFAULT_EXPIRE_MINUTES))

    if not secret_key:
        raise ValueError("SECRET_KEY should be set. Check if it is in .env.")

    try:
        expire_minutes_int = int(expire_minutes)
    except ValueError as err:
        raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES should be an integer.") from err

    return secret_key, algorithm, expire_minutes_int


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT for the authenticated subject."""
    secret_key, algorithm, expire_minutes = _get_token_settings()

    to_encode: dict[str, str | int] = {"sub": subject}
    if expires_delta is None:
        expires_at = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    else:
        expires_at = datetime.now(UTC) + expires_delta

    to_encode.update({"exp": int(expires_at.timestamp())})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)

    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """Decode a signed JWT and return its subject as token data."""
    secret_key, algorithm, _ = _get_token_settings()

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
        return TokenData(email=email)

    except InvalidTokenError as err:
        raise credentials_exception from err
