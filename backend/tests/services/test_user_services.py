from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from compliance.db.models import Role, User
from compliance.services.schemas import UserCreate
from compliance.services.users import (
    UserConflictError,
    UserEmailConflictError,
    bootstrap_first_admin,
    get_users,
    post_new_user,
)

TEST_PASSWORD = "correct-password"  # noqa: S105


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

        session.add.side_effect = _populate_defaults
        user = UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
        )

        with patch(
            "compliance.services.users._hash_password",
            return_value="hashed-password",
        ) as mock_hash_password:
            result = post_new_user(session, user)

        session.add.assert_called_once()
        added_user = session.add.call_args.args[0]
        mock_hash_password.assert_called_once_with(TEST_PASSWORD)

        assert result.id == added_user.id
        assert isinstance(added_user, User)
        assert added_user.full_name == "Alice Inspector"
        assert added_user.email == "alice@example.com"
        assert not hasattr(added_user, "password")
        assert added_user.hashed_password == "hashed-password"  # noqa: S105
        assert added_user.role == Role.VIEWER
        assert added_user.is_active is True
        assert added_user.created_at.tzinfo is UTC
        assert not hasattr(result, "password")

    def test_uses_supplied_role_and_active_status(self) -> None:
        session = MagicMock()

        def _populate_id(added_user: User) -> None:
            added_user.id = 10

        session.add.side_effect = _populate_id
        user = UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
            role=Role.ADMIN,
            is_active=False,
        )

        result = post_new_user(session, user)

        added_user = session.add.call_args.args[0]
        assert added_user.role == Role.ADMIN
        assert added_user.is_active is False
        assert result.role == Role.ADMIN
        assert result.is_active is False

    def test_rolls_back_and_raises_conflict_when_insert_conflicts(
        self, integrity_error_factory
    ) -> None:
        session = MagicMock()
        session.commit.side_effect = integrity_error_factory()
        user = UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
        )

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
        user = UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
        )

        with pytest.raises(UserEmailConflictError):
            post_new_user(session, user)

        session.rollback.assert_called_once_with()


class TestBootstrapFirstAdmin:
    def test_creates_active_admin_when_no_active_admin_exists(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None

        with patch(
            "compliance.services.users.post_new_user",
            return_value=_user(role=Role.ADMIN),
        ) as mock_post_new_user:
            result = bootstrap_first_admin(
                session,
                full_name="Alice Admin",
                email="admin@example.com",
                password=TEST_PASSWORD,
            )

        assert result.created is True
        assert result.user is not None
        assert result.user.role == Role.ADMIN
        assert result.user.is_active is True

        user_create = mock_post_new_user.call_args.args[1]
        assert user_create.full_name == "Alice Admin"
        assert user_create.email == "admin@example.com"
        assert user_create.password == TEST_PASSWORD
        assert user_create.role == Role.ADMIN
        assert user_create.is_active is True

    def test_noops_when_active_admin_exists(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = _user(
            role=Role.ADMIN
        )

        with patch("compliance.services.users.post_new_user") as mock_post_new_user:
            result = bootstrap_first_admin(
                session,
                full_name="Alice Admin",
                email="admin@example.com",
                password=TEST_PASSWORD,
            )

        assert result.created is False
        assert result.user is None
        mock_post_new_user.assert_not_called()

    def test_checks_only_active_admins(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None

        with patch(
            "compliance.services.users.post_new_user",
            return_value=_user(role=Role.ADMIN),
        ):
            bootstrap_first_admin(
                session,
                full_name="Alice Admin",
                email="admin@example.com",
                password=TEST_PASSWORD,
            )

        stmt = session.execute.call_args.args[0]
        assert "users.role = :role_1" in str(stmt)
        assert "users.is_active IS true" in str(stmt)

    def test_propagates_email_conflict_when_requested_email_exists(self) -> None:
        session = MagicMock()
        session.execute.return_value.scalars.return_value.first.return_value = None

        with (
            patch(
                "compliance.services.users.post_new_user",
                side_effect=UserEmailConflictError("email exists"),
            ),
            pytest.raises(UserEmailConflictError),
        ):
            bootstrap_first_admin(
                session,
                full_name="Alice Admin",
                email="admin@example.com",
                password=TEST_PASSWORD,
            )
