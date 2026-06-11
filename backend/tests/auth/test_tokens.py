from datetime import UTC, datetime, timedelta

import jwt
import pytest
from compliance.auth import tokens
from compliance.auth.tokens import (
    _get_token_settings,
    create_access_token,
    decode_access_token,
)
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(
        "compliance.auth.tokens.load_dotenv", lambda *args, **kwargs: None
    )


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "12345678901234567890123456789012")
    monkeypatch.setenv("ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")


class TestGetTokenSettings:
    def test_reads_token_settings_from_environment(self, token_env) -> None:
        assert _get_token_settings() == (
            "12345678901234567890123456789012",
            "HS256",
            30,
        )

    def test_uses_defaults_for_optional_settings(self, monkeypatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "12345678901234567890123456789012")
        monkeypatch.delenv("ALGORITHM", raising=False)
        monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

        assert _get_token_settings() == (
            "12345678901234567890123456789012",
            "HS256",
            tokens._DEFAULT_EXPIRE_MINUTES,
        )

    def test_raises_when_secret_key_is_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("SECRET_KEY", raising=False)

        with pytest.raises(ValueError, match="SECRET_KEY"):
            _get_token_settings()

    def test_raises_when_expire_minutes_is_not_an_integer(self, monkeypatch) -> None:
        monkeypatch.setenv("SECRET_KEY", "12345678901234567890123456789012")
        monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "soon")

        with pytest.raises(ValueError, match="ACCESS_TOKEN_EXPIRE_MINUTES"):
            _get_token_settings()


class TestCreateAccessToken:
    def test_creates_signed_token_with_subject_and_expiration(self, token_env) -> None:
        token = create_access_token("42", expires_delta=timedelta(minutes=5))

        payload = jwt.decode(
            token,
            "12345678901234567890123456789012",
            algorithms=["HS256"],
        )
        assert payload["sub"] == "42"
        assert isinstance(payload["exp"], int)

    def test_uses_configured_default_expiration(self, token_env) -> None:
        before = datetime.now(UTC)
        token = create_access_token("42")
        after = datetime.now(UTC)

        payload = jwt.decode(
            token,
            "12345678901234567890123456789012",
            algorithms=["HS256"],
        )
        expires_at = datetime.fromtimestamp(payload["exp"], tz=UTC)

        assert before + timedelta(minutes=30, seconds=-1) <= expires_at
        assert expires_at <= after + timedelta(minutes=30)


class TestDecodeAccessToken:
    def test_returns_token_data_for_valid_token(self, token_env) -> None:
        token = create_access_token("42")

        result = decode_access_token(token)

        assert result.user_id == "42"

    def test_raises_unauthorized_for_invalid_token(self, token_env) -> None:
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("not-a-token")

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Could not validate credentials"

    def test_raises_unauthorized_when_subject_is_missing(self, token_env) -> None:
        token = jwt.encode(
            {"exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())},
            "12345678901234567890123456789012",
            algorithm="HS256",
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == 401
