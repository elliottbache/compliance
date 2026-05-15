from datetime import UTC, datetime

import pytest
from compliance.services.schemas import ClientOut
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
