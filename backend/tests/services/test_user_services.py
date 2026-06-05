from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import Role, User
from compliance.services.schemas import UserCreate
from compliance.services.users import (
    UserConflictError,
    UserEmailConflictError,
    get_users,
    post_new_user,
)


def _user(**overrides) -> User:
    user = User(
        id=10,
        email="alice@example.com",
        hashed_password="dummy_hash",  # noqa: S106
        full_name="Alice Inspector",
        role=Role.VIEWER,
        is_active=True,
        created_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
    )
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


class TestGetUsers:
    def test_returns_users_from_session(self) -> None:
        session = MagicMock()
        users = [
            _user(id=10, full_name="Alice Inspector"),
            _user(id=11, full_name="Bob Reviewer", email="bob@example.com"),
        ]
        session.execute.return_value.scalars.return_value.all.return_value = users

        result = get_users(session, limit=10, offset=5)

        assert result == users

    def test_orders_users_by_full_name_then_id(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_users(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "ORDER BY users.full_name, users.id" in str(stmt)

    def test_excludes_inactive_users_by_default(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_users(session, limit=None, offset=0)

        stmt = session.execute.call_args.args[0]
        assert "users.is_active IS true" in str(stmt)

    def test_includes_inactive_users_when_requested(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.all.return_value = []

        get_users(session, limit=None, offset=0, include_inactive=True)

        stmt = session.execute.call_args.args[0]
        assert "users.is_active IS true" not in str(stmt)


class TestPostNewUser:
    def test_adds_and_commits_new_user(self) -> None:
        session = MagicMock()

        def _populate_defaults(added_user: User) -> None:
            added_user.id = 10
            added_user.role = Role.VIEWER
            added_user.is_active = True

        session.add.side_effect = _populate_defaults
        user = UserCreate(full_name="Alice Inspector", email="alice@example.com")

        result = post_new_user(session, user)

        session.add.assert_called_once()
        added_user = session.add.call_args.args[0]

        assert result.id == added_user.id
        assert isinstance(added_user, User)
        assert added_user.full_name == "Alice Inspector"
        assert added_user.email == "alice@example.com"
        assert added_user.hashed_password == "dummy_hash"  # noqa: S105
        assert added_user.role == Role.VIEWER
        assert added_user.is_active is True
        assert added_user.created_at.tzinfo is UTC

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory()
        user = UserCreate(full_name="Alice Inspector", email="alice@example.com")

        with pytest.raises(UserConflictError):
            post_new_user(session, user)

        session.add.assert_called_once()
        session.commit.assert_called_once_with()
        session.rollback.assert_called_once_with()

    def test_raises_email_conflict_when_email_exists(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory("uq_users_email")
        user = UserCreate(full_name="Alice Inspector", email="alice@example.com")

        with pytest.raises(UserEmailConflictError):
            post_new_user(session, user)

        session.rollback.assert_called_once_with()
