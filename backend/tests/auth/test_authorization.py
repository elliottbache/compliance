from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from compliance.auth.authorization import (
    get_active_user,
    get_current_user,
    require_role,
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


class TestGetCurrentUser:
    def test_returns_user_from_valid_bearer_token(self) -> None:
        session = object()
        user = _user_record(email="admin@example.com", role=Role.ADMIN)

        with (
            patch("compliance.auth.authorization.decode_access_token") as mock_decode,
            patch(
                "compliance.auth.authorization._get_user_in_db",
                return_value=UserInDB.model_validate(user),
            ) as mock_get_user,
        ):
            mock_decode.return_value = SimpleNamespace(email="admin@example.com")

            result = get_current_user(session, "token")

        assert result.email == "admin@example.com"
        assert result.role == Role.ADMIN
        assert not hasattr(result, "hashed_password")
        mock_get_user.assert_called_once_with(session, "admin@example.com")

    def test_raises_unauthorized_when_user_is_missing(self) -> None:
        session = object()

        with (
            patch(
                "compliance.auth.authorization.decode_access_token",
                return_value=SimpleNamespace(email="missing@example.com"),
            ),
            patch("compliance.auth.authorization._get_user_in_db", return_value=None),
            pytest.raises(HTTPException) as exc_info,
        ):
            get_current_user(session, "token")

        assert exc_info.value.status_code == 401


class TestGetActiveUser:
    def test_returns_active_user(self) -> None:
        user = UserOut.model_validate(_user_record(is_active=True))

        assert get_active_user(user) is user

    def test_raises_for_inactive_user(self) -> None:
        user = UserOut.model_validate(_user_record(is_active=False))

        with pytest.raises(HTTPException) as exc_info:
            get_active_user(user)

        assert exc_info.value.status_code == 400


class TestRequireRole:
    def test_allows_matching_role(self) -> None:
        user = UserOut.model_validate(_user_record(role=Role.REVIEWER))
        dependency = require_role(Role.REVIEWER)

        assert dependency(user) is user

    def test_allows_higher_role(self) -> None:
        user = UserOut.model_validate(_user_record(role=Role.ADMIN))
        dependency = require_role(Role.REVIEWER)

        assert dependency(user) is user

    def test_raises_for_lower_role(self) -> None:
        user = UserOut.model_validate(_user_record(role=Role.VIEWER))
        dependency = require_role(Role.REVIEWER)

        with pytest.raises(HTTPException) as exc_info:
            dependency(user)

        assert exc_info.value.status_code == 403
