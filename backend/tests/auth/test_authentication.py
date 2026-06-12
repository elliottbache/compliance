from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from compliance.auth import authentication
from compliance.auth.authentication import (
    _get_token_settings,
    _get_user_in_db,
    _hash_password,
    _verify_password,
    authenticate_user,
    create_access_token,
    decode_access_token,
)
from compliance.db.models import Role
from compliance.services.schemas import UserInDB, UserOut
from fastapi import HTTPException


def _user_record(**overrides) -> SimpleNamespace:
    user = SimpleNamespace(
        id=42,
        full_name="Alice Inspector",
        email="alice@example.com",
        role=Role.VIEWER,
        is_active=True,
        created_at=datetime(2026, 6, 11, 9, 0, tzinfo=UTC),
        hashed_password="stored-hash",  # noqa: S106
    )
    user.__dict__.update(overrides)
    return user


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(
        "compliance.auth.authentication.load_dotenv", lambda *args, **kwargs: None
    )


@pytest.fixture
def token_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "12345678901234567890123456789012")
    monkeypatch.setenv("ALGORITHM", "HS256")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")


class TestGetUserInDB:
    def test_returns_validated_user_when_email_exists(self) -> None:
        session = MagicMock()
        user = _user_record()
        session.execute.return_value.scalars.return_value.first.return_value = user

        result = _get_user_in_db(session, "alice@example.com")

        assert result is not None
        assert result.id == 42
        assert result.email == "alice@example.com"
        assert result.hashed_password == "stored-hash"  # noqa: S105
        assert session.execute.call_count == 1

    def test_returns_none_when_email_does_not_exist(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None

        result = _get_user_in_db(session, "missing@example.com")

        assert result is None
        assert session.execute.call_count == 1


class TestAuthenticateUser:
    def test_returns_public_user_when_password_matches(self) -> None:
        session = object()
        user = UserInDB.model_validate(_user_record())

        with (
            patch(
                "compliance.auth.authentication._get_user_in_db",
                return_value=user,
            ) as mock_get_user,
            patch(
                "compliance.auth.authentication._verify_password",
                return_value=True,
            ) as mock_verify_password,
        ):
            result = authenticate_user(session, "alice@example.com", "correct-password")

        expected_user = UserOut.model_validate(
            user.model_dump(exclude={"hashed_password"})
        )
        assert result == expected_user
        assert not hasattr(result, "hashed_password")
        mock_get_user.assert_called_once_with(session, "alice@example.com")
        mock_verify_password.assert_called_once_with("correct-password", "stored-hash")

    def test_returns_none_when_user_does_not_exist(self) -> None:
        session = object()

        with (
            patch(
                "compliance.auth.authentication._get_user_in_db",
                return_value=None,
            ),
            patch(
                "compliance.auth.authentication._verify_password",
                return_value=False,
            ) as mock_verify_password,
        ):
            result = authenticate_user(session, "alice@example.com", "wrong-password")

        assert result is None
        mock_verify_password.assert_called_once()

    def test_returns_none_when_password_does_not_match(self) -> None:
        session = object()
        user = UserInDB.model_validate(_user_record())

        with (
            patch(
                "compliance.auth.authentication._get_user_in_db",
                return_value=user,
            ),
            patch(
                "compliance.auth.authentication._verify_password",
                return_value=False,
            ) as mock_verify_password,
        ):
            result = authenticate_user(session, "alice@example.com", "wrong-password")

        assert result is None
        mock_verify_password.assert_called_once_with("wrong-password", "stored-hash")


class TestPasswordHashing:
    def test_hashed_password_verifies_original_password(self) -> None:
        hashed_password = _hash_password("correct-password")

        assert _verify_password("correct-password", hashed_password) is True

    def test_hashed_password_rejects_different_password(self) -> None:
        hashed_password = _hash_password("correct-password")

        assert _verify_password("wrong-password", hashed_password) is False


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
            authentication._DEFAULT_EXPIRE_MINUTES,
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
        token = create_access_token(
            "alice@example.com", expires_delta=timedelta(minutes=5)
        )

        payload = jwt.decode(
            token,
            "12345678901234567890123456789012",
            algorithms=["HS256"],
        )
        assert payload["sub"] == "alice@example.com"
        assert isinstance(payload["exp"], int)

    def test_uses_configured_default_expiration(self, token_env) -> None:
        before = datetime.now(UTC)
        token = create_access_token("alice@example.com")
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
        token = create_access_token("alice@example.com")

        result = decode_access_token(token)

        assert result.email == "alice@example.com"

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
