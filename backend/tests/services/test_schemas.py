from datetime import UTC, datetime

import pytest
from compliance.db.models import Role
from compliance.services.schemas import ClientOut, UserCreate, UserOut
from pydantic import ValidationError


def _client_payload(**overrides):
    payload = {
        "nif": "A1234567B",
        "company_name": "Acme Corp",
        "contact_name": "John Doe",
        "email": None,
        "telephone": None,
        "archived_at": None,
        "archive_reason": None,
    }
    payload.update(overrides)
    return payload


class TestClientOut:
    def test_rejects_naive_archived_at(self) -> None:
        with pytest.raises(ValidationError):
            ClientOut(**_client_payload(archived_at=datetime(2026, 5, 8, 10, 0)))

    def test_accepts_timezone_aware_archived_at(self) -> None:
        archived_at = datetime(2026, 5, 8, 10, 0, tzinfo=UTC)

        client = ClientOut(**_client_payload(archived_at=archived_at))

        assert client.archived_at == archived_at


class TestUserCreate:
    def test_defaults_role_and_active_status(self) -> None:
        user = UserCreate(full_name="Alice Inspector", email="alice@example.com")

        assert user.role == Role.VIEWER
        assert user.is_active is True

    def test_accepts_role_and_active_status(self) -> None:
        user = UserCreate(
            full_name="Alice Inspector",
            email="alice@example.com",
            role=Role.ADMIN,
            is_active=False,
        )

        assert user.role == Role.ADMIN
        assert user.is_active is False


class TestUserOut:
    def test_inherits_user_create_fields(self) -> None:
        user = UserOut(
            id=10,
            full_name="Alice Inspector",
            email="alice@example.com",
            role=Role.REVIEWER,
            is_active=False,
            created_at=datetime(2026, 6, 5, 10, 0, tzinfo=UTC),
        )

        assert user.role == Role.REVIEWER
        assert user.is_active is False
