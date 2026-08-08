import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from compliance.api.routers.auth import post_auth_token_route
from compliance.db.models import AuditAction
from fastapi import HTTPException


def _form_data(username: str, password: str) -> SimpleNamespace:
    return SimpleNamespace(username=username, password=password)


class TestPostAuthTokenRoute:
    def test_returns_bearer_token_for_active_user(self) -> None:
        session = MagicMock()
        user = SimpleNamespace(id=42, email="alice@example.com", is_active=True)

        with (
            patch(
                "compliance.api.routers.auth.authenticate_user",
                return_value=user,
            ) as mock_authenticate_user,
            patch(
                "compliance.api.routers.auth.create_access_token",
                return_value="encoded-token",
            ) as mock_create_access_token,
        ):
            result = post_auth_token_route(
                session, _form_data("alice@example.com", "correct-password")
            )

        assert result.access_token == "encoded-token"  # noqa: S105
        assert result.token_type == "bearer"  # noqa: S105
        mock_authenticate_user.assert_called_once_with(
            session, "alice@example.com", "correct-password"
        )
        mock_create_access_token.assert_called_once_with("alice@example.com")
        audit_event = session.add.call_args.args[0]
        assert audit_event.action == AuditAction.LOGIN_SUCCESS
        assert audit_event.actor_user_id == 42
        assert audit_event.actor_email == "alice@example.com"
        session.commit.assert_called_once_with()

    def test_raises_unauthorized_when_credentials_are_invalid(self, caplog) -> None:
        session = MagicMock()

        with (
            caplog.at_level(logging.WARNING, logger="compliance.api.routers.auth"),
            patch(
                "compliance.api.routers.auth.authenticate_user",
                return_value=None,
            ),
            patch("compliance.api.routers.auth.create_access_token") as mock_create,
            pytest.raises(HTTPException) as exc_info,
        ):
            post_auth_token_route(
                session, _form_data("alice@example.com", "wrong-password")
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Incorrect username or password"
        mock_create.assert_not_called()
        audit_event = session.add.call_args.args[0]
        assert audit_event.action == AuditAction.LOGIN_FAILED
        assert audit_event.actor_user_id is None
        assert audit_event.actor_email == "alice@example.com"
        assert audit_event.context == {"reason": "invalid_credentials"}
        session.commit.assert_called_once_with()
        [record] = [
            record
            for record in caplog.records
            if record.message == "Authentication failed."
        ]
        assert record.event == "auth_failed"
        assert record.actor_user_id is None
        assert record.actor_email == "alice@example.com"
        assert record.reason == "invalid_credentials"
        assert record.status_code == 401

    def test_raises_forbidden_when_user_is_inactive(self, caplog) -> None:
        session = MagicMock()
        user = SimpleNamespace(id=42, email="alice@example.com", is_active=False)

        with (
            caplog.at_level(logging.WARNING, logger="compliance.api.routers.auth"),
            patch(
                "compliance.api.routers.auth.authenticate_user",
                return_value=user,
            ),
            patch("compliance.api.routers.auth.create_access_token") as mock_create,
            pytest.raises(HTTPException) as exc_info,
        ):
            post_auth_token_route(
                session, _form_data("alice@example.com", "correct-password")
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden access"
        mock_create.assert_not_called()
        audit_event = session.add.call_args.args[0]
        assert audit_event.action == AuditAction.LOGIN_FAILED
        assert audit_event.actor_user_id == 42
        assert audit_event.actor_email == "alice@example.com"
        assert audit_event.context == {"reason": "inactive_user"}
        session.commit.assert_called_once_with()
        [record] = [
            record
            for record in caplog.records
            if record.message == "Authentication failed."
        ]
        assert record.event == "auth_failed"
        assert record.actor_user_id == 42
        assert record.actor_email == "alice@example.com"
        assert record.reason == "inactive_user"
        assert record.status_code == 403
