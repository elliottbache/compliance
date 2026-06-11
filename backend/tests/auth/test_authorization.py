from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from compliance.auth.authentication import authenticate_user, get_user
from compliance.auth.authorization import (
    get_active_user,
    get_current_user,
    require_role,
)
from compliance.db.models import Role
from compliance.services.schemas import UserInDB
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


class TestGetUser:
    def test_returns_validated_user_when_email_exists(self) -> None:
        session = MagicMock()
        user = _user_record()
        session.execute.return_value.scalars.return_value.first.return_value = user

        result = get_user(session, "alice@example.com")

        assert result is not None
        assert result.id == 42
        assert result.email == "alice@example.com"
        assert result.hashed_password == "stored-hash"  # noqa: S105
        assert session.execute.call_count == 1

    def test_returns_none_when_email_does_not_exist(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None

        result = get_user(session, "missing@example.com")

        assert result is None
        assert session.execute.call_count == 1


class TestAuthenticateUser:
    def test_returns_user_when_password_matches(self) -> None:
        session = object()
        user = SimpleNamespace(hashed_password="stored-hash")  # noqa: S106

        with (
            patch(
                "compliance.auth.authentication.get_user",
                return_value=user,
            ) as mock_get_user,
            patch(
                "compliance.auth.authentication._verify_password",
                return_value=True,
            ) as mock_verify_password,
        ):
            result = authenticate_user(session, "alice@example.com", "correct-password")

        assert result is user
        mock_get_user.assert_called_once_with(session, "alice@example.com")
        mock_verify_password.assert_called_once_with("correct-password", "stored-hash")

    def test_returns_none_when_user_does_not_exist(self) -> None:
        session = object()

        with (
            patch(
                "compliance.auth.authentication.get_user",
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
        user = SimpleNamespace(hashed_password="stored-hash")  # noqa: S106

        with (
            patch(
                "compliance.auth.authentication.get_user",
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


class TestGetCurrentUser:
    def test_returns_user_from_valid_bearer_token(self) -> None:
        session = object()
        user = _user_record(email="admin@example.com", role=Role.ADMIN)

        with (
            patch(
                "compliance.auth.authorization._get_token_settings",
                return_value=("secret", "HS256", 30),
            ),
            patch("compliance.auth.authorization.jwt.decode") as mock_decode,
            patch(
                "compliance.auth.authorization.get_user",
                return_value=UserInDB.model_validate(user),
            ) as mock_get_user,
        ):
            mock_decode.return_value = {"sub": "admin@example.com"}

            result = get_current_user(session, "token")

        assert result.email == "admin@example.com"
        assert result.role == Role.ADMIN
        mock_get_user.assert_called_once_with(session, "admin@example.com")

    def test_raises_unauthorized_when_user_is_missing(self) -> None:
        session = object()

        with (
            patch(
                "compliance.auth.authorization._get_token_settings",
                return_value=("secret", "HS256", 30),
            ),
            patch(
                "compliance.auth.authorization.jwt.decode",
                return_value={"sub": "missing@example.com"},
            ),
            patch("compliance.auth.authorization.get_user", return_value=None),
            pytest.raises(HTTPException) as exc_info,
        ):
            get_current_user(session, "token")

        assert exc_info.value.status_code == 401


class TestGetActiveUser:
    def test_returns_active_user(self) -> None:
        user = UserInDB.model_validate(_user_record(is_active=True))

        assert get_active_user(user) is user

    def test_raises_for_inactive_user(self) -> None:
        user = UserInDB.model_validate(_user_record(is_active=False))

        with pytest.raises(HTTPException) as exc_info:
            get_active_user(user)

        assert exc_info.value.status_code == 400


class TestRequireRole:
    def test_allows_matching_role(self) -> None:
        user = UserInDB.model_validate(_user_record(role=Role.REVIEWER))
        dependency = require_role(Role.REVIEWER)

        assert dependency(user) is user

    def test_allows_higher_role(self) -> None:
        user = UserInDB.model_validate(_user_record(role=Role.ADMIN))
        dependency = require_role(Role.REVIEWER)

        assert dependency(user) is user

    def test_raises_for_lower_role(self) -> None:
        user = UserInDB.model_validate(_user_record(role=Role.VIEWER))
        dependency = require_role(Role.REVIEWER)

        with pytest.raises(HTTPException) as exc_info:
            dependency(user)

        assert exc_info.value.status_code == 403
