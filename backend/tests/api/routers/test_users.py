from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from compliance.api.routers import users as users_router
from compliance.db.models import Role
from fastapi import HTTPException


def _user_record(**overrides):
    user = SimpleNamespace(
        id=10,
        full_name="Alice Inspector",
        email="alice@example.com",
        role=Role.VIEWER,
        is_active=True,
        created_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
    )
    user.__dict__.update(**overrides)
    return user


class TestGetUsersRoute:
    # TestClient
    def test_route_returns_user_json(self, client, mock_db, monkeypatch):
        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is mock_db
            assert limit == 2
            assert offset == 1
            assert include_inactive is False
            return [
                _user_record(),
                _user_record(
                    id=11,
                    full_name="Bob Reviewer",
                    email="bob@example.com",
                    role=Role.REVIEWER,
                ),
            ]

        monkeypatch.setattr(users_router, "get_users", fake_get_users)

        response = client.get(
            "/users?limit=2&offset=1",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": 10,
                "full_name": "Alice Inspector",
                "email": "alice@example.com",
                "role": "viewer",
                "is_active": True,
                "created_at": "2026-06-05T10:00:00Z",
            },
            {
                "id": 11,
                "full_name": "Bob Reviewer",
                "email": "bob@example.com",
                "role": "reviewer",
                "is_active": True,
                "created_at": "2026-06-05T10:00:00Z",
            },
        ]

    def test_route_includes_inactive_users_when_requested(
        self, client, mock_db, monkeypatch
    ):
        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is mock_db
            assert include_inactive is True
            return [_user_record(is_active=False)]

        monkeypatch.setattr(users_router, "get_users", fake_get_users)

        response = client.get(
            "/users?include_inactive=true",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        assert response.json()[0]["is_active"] is False

    def test_route_returns_422_when_limit_is_invalid(self, client):
        response = client.get(
            "/users?limit=0",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 422

    # unittests
    def test_returns_users(self, monkeypatch) -> None:
        fake_session = object()
        users = [_user_record()]
        expected_users = [users_router.UserOut.model_validate(user) for user in users]

        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is fake_session
            assert limit == 10
            assert offset == 5
            assert include_inactive is False
            return users

        monkeypatch.setattr(users_router, "get_users", fake_get_users)

        result = users_router.get_users_route(
            fake_session, token="test-token", limit=10, offset=5  # noqa: S106
        )

        assert result == expected_users

    def test_registers_user_list_response_model(self, main_module) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/users"
            and "GET" in getattr(route, "methods", set())
        )

        assert route.response_model == list[users_router.UserOut]


class TestPostNewUserRoute:
    # TestClient
    def test_route_returns_user_json_when_created(self, client, mock_db, monkeypatch):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            assert user_record.full_name == "Alice Inspector"
            assert user_record.email == "alice@example.com"
            return _user_record()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={"full_name": "Alice Inspector", "email": "alice@example.com"},
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 10,
            "full_name": "Alice Inspector",
            "email": "alice@example.com",
            "role": "viewer",
            "is_active": True,
            "created_at": "2026-06-05T10:00:00Z",
        }

    def test_route_returns_409_when_user_email_already_exists(
        self, client, mock_db, monkeypatch
    ):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            raise users_router.UserEmailConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={"full_name": "Alice Inspector", "email": "alice@example.com"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "User with email alice@example.com already exists."
        }

    def test_route_returns_409_when_user_conflicts(self, client, mock_db, monkeypatch):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            raise users_router.UserConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={"full_name": "Alice Inspector", "email": "alice@example.com"},
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "User was not added because of a data conflict."
        }

    def test_route_returns_422_when_user_is_invalid(self, client):
        response = client.post(
            "/users", json={"full_name": "", "email": "not-an-email"}
        )

        assert response.status_code == 422

    # unittests
    def test_returns_created_user(self, monkeypatch) -> None:
        fake_session = object()
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
        )
        expected_user = users_router.UserOut.model_validate(_user_record())

        def fake_post_new_user(session, user_info):
            assert session is fake_session
            assert user_info is user
            return expected_user

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        result = users_router.post_new_user_route(fake_session, user)

        assert result == expected_user

    def test_returns_409_when_user_email_already_exists(self, monkeypatch) -> None:
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
        )

        def fake_post_new_user(session, user_info):
            raise users_router.UserEmailConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        with pytest.raises(HTTPException) as exc_info:
            users_router.post_new_user_route(object(), user)

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail == "User with email alice@example.com already exists."
        )

    def test_returns_409_when_user_is_not_created(self, monkeypatch) -> None:
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
        )

        def fake_post_new_user(session, user_info):
            raise users_router.UserConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        with pytest.raises(HTTPException) as exc_info:
            users_router.post_new_user_route(object(), user)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "User was not added because of a data conflict."

    def test_registers_user_response_model_and_created_status(
        self, main_module
    ) -> None:
        route = next(
            route
            for route in main_module.app.routes
            if getattr(route, "path", None) == "/users"
            and "POST" in getattr(route, "methods", set())
        )

        assert route.response_model is users_router.UserOut
        assert route.status_code == 201
