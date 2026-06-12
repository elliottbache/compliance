import pytest
from compliance.api.routers import users as users_router
from compliance.db.models import Role
from fastapi import HTTPException

TEST_PASSWORD = "correct-password"  # noqa: S105


@pytest.mark.usefixtures("admin_user_override")
class TestGetUsersRouteClient:
    # TestClient
    def test_route_returns_user_json(
        self, client, mock_db, user_record_factory, monkeypatch
    ):
        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is mock_db
            assert limit == 2
            assert offset == 1
            assert include_inactive is False
            return [
                user_record_factory(),
                user_record_factory(
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
        self, client, mock_db, user_record_factory, monkeypatch
    ):
        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is mock_db
            assert include_inactive is True
            return [user_record_factory(is_active=False)]

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


class TestGetUsersRouteUnit:
    def test_returns_users(self, user_record_factory, monkeypatch) -> None:
        fake_session = object()
        users = [user_record_factory()]
        expected_users = [users_router.UserOut.model_validate(user) for user in users]

        def fake_get_users(session, *, limit, offset, include_inactive=False):
            assert session is fake_session
            assert limit == 10
            assert offset == 5
            assert include_inactive is False
            return users

        monkeypatch.setattr(users_router, "get_users", fake_get_users)

        result = users_router.get_users_route(
            fake_session,
            _authorized_user=object(),
            token="test-token",  # noqa: S106
            limit=10,
            offset=5,
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


@pytest.mark.usefixtures("admin_user_override")
class TestPostNewUserRouteClient:
    # TestClient
    def test_route_returns_user_json_when_created(
        self, client, mock_db, admin_user_override, user_record_factory, monkeypatch
    ):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            assert user_record.full_name == "Alice Inspector"
            assert user_record.email == "alice@example.com"
            assert user_record.password == TEST_PASSWORD
            assert user_record.role == Role.ADMIN
            assert user_record.is_active is False
            return user_record_factory(role=Role.ADMIN, is_active=False)

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={
                "full_name": "Alice Inspector",
                "email": "alice@example.com",
                "password": TEST_PASSWORD,
                "role": "admin",
                "is_active": False,
            },
        )

        assert response.status_code == 201
        assert response.json() == {
            "id": 10,
            "full_name": "Alice Inspector",
            "email": "alice@example.com",
            "role": "admin",
            "is_active": False,
            "created_at": "2026-06-05T10:00:00Z",
        }

    def test_route_returns_409_when_user_email_already_exists(
        self, client, mock_db, admin_user_override, monkeypatch
    ):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            raise users_router.UserEmailConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={
                "full_name": "Alice Inspector",
                "email": "alice@example.com",
                "password": TEST_PASSWORD,
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "User with email alice@example.com already exists."
        }

    def test_route_returns_409_when_user_conflicts(
        self, client, mock_db, admin_user_override, monkeypatch
    ):
        def fake_post_new_user(session, user_record):
            assert session is mock_db
            raise users_router.UserConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        response = client.post(
            "/users",
            json={
                "full_name": "Alice Inspector",
                "email": "alice@example.com",
                "password": TEST_PASSWORD,
            },
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "User was not added because of a data conflict."
        }

    def test_route_returns_422_when_user_is_invalid(self, client, admin_user_override):
        response = client.post(
            "/users", json={"full_name": "", "email": "not-an-email"}
        )

        assert response.status_code == 422


class TestPostNewUserRouteUnit:
    def test_returns_created_user(self, user_record_factory, monkeypatch) -> None:
        fake_session = object()
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
            role=Role.ADMIN,
            is_active=False,
        )
        expected_user = users_router.UserOut.model_validate(
            user_record_factory(role=Role.ADMIN, is_active=False)
        )

        def fake_post_new_user(session, user_info):
            assert session is fake_session
            assert user_info is user
            assert user_info.password == TEST_PASSWORD
            assert user_info.role == Role.ADMIN
            assert user_info.is_active is False
            return expected_user

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        result = users_router.post_new_user_route(
            fake_session,
            user=user,
            _authorized_user=user_record_factory(role=Role.ADMIN),
        )

        assert result == expected_user

    def test_returns_409_when_user_email_already_exists(
        self, user_record_factory, monkeypatch
    ) -> None:
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
        )

        def fake_post_new_user(session, user_info):
            raise users_router.UserEmailConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        with pytest.raises(HTTPException) as exc_info:
            users_router.post_new_user_route(
                object(),
                user=user,
                _authorized_user=user_record_factory(role=Role.ADMIN),
            )

        assert exc_info.value.status_code == 409
        assert (
            exc_info.value.detail == "User with email alice@example.com already exists."
        )

    def test_returns_409_when_user_is_not_created(
        self, user_record_factory, monkeypatch
    ) -> None:
        user = users_router.UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            password=TEST_PASSWORD,
        )

        def fake_post_new_user(session, user_info):
            raise users_router.UserConflictError()

        monkeypatch.setattr(users_router, "post_new_user", fake_post_new_user)

        with pytest.raises(HTTPException) as exc_info:
            users_router.post_new_user_route(
                object(),
                user=user,
                _authorized_user=user_record_factory(role=Role.ADMIN),
            )

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
