from datetime import UTC, datetime, timedelta
from os import getenv

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel

from compliance._helpers import ROOT_DIR

_DEFAULT_EXPIRE_MINUTES = 30
_DOTENV_PATH = ROOT_DIR / "backend" / ".env"


class TokenData(BaseModel):
    """Represents the authenticated user identity extracted from a JWT."""

    user_id: str | None = None


class Token(BaseModel):
    """Represents a bearer token response returned by the auth endpoint."""

    access_token: str
    token_type: str


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
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return TokenData(user_id=user_id)

    except InvalidTokenError as err:
        raise credentials_exception from err
