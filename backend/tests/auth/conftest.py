from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from compliance.db.models import Role


@pytest.fixture
def user_record_factory():
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

    return _user_record
