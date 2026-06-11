from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from compliance.auth.authorization import authenticate_user, get_user
from compliance.db.models import Role


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
                "compliance.auth.authorization.get_user",
                return_value=user,
            ) as mock_get_user,
            patch(
                "compliance.auth.authorization.verify_password",
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
                "compliance.auth.authorization.get_user",
                return_value=None,
            ),
            patch(
                "compliance.auth.authorization.verify_password",
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
                "compliance.auth.authorization.get_user",
                return_value=user,
            ),
            patch(
                "compliance.auth.authorization.verify_password",
                return_value=False,
            ) as mock_verify_password,
        ):
            result = authenticate_user(session, "alice@example.com", "wrong-password")

        assert result is None
        mock_verify_password.assert_called_once_with("wrong-password", "stored-hash")
