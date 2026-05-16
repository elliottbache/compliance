from datetime import UTC, datetime

import pytest
from compliance.db.models import (
    Attachment,
    Certification,
    Certifier,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)


def test_finding_attachments_primary_key_excludes_certification_id() -> None:
    pk_columns = {
        column.name for column in FindingAttachment.__table__.primary_key.columns
    }

    assert pk_columns == {"finding_id", "attachment_id"}


@pytest.mark.parametrize(
    "model",
    [
        Attachment,
        Certification,
        Certifier,
        Client,
        Finding,
        Regulation,
        Rule,
        Site,
    ],
)
def test_archived_at_columns_are_timezone_aware(model) -> None:
    archived_at_column = model.__table__.columns["archived_at"]

    assert archived_at_column.type.timezone is True


class TestSqliteDatetimePolicy:
    def test_loaded_archived_at_is_normalized_to_utc(self, sqlite_session) -> None:
        archived_at = datetime(2026, 5, 16, 8, 0, tzinfo=UTC)
        client = Client(
            nif="A1234567B",
            company_name="Acme Corp",
            contact_name="John Doe",
            email=None,
            telephone=None,
            archived_at=archived_at,
            archive_reason="duplicate",
        )
        sqlite_session.add(client)
        sqlite_session.commit()
        sqlite_session.expunge_all()

        result = sqlite_session.get(Client, "A1234567B")

        assert result.archived_at.tzinfo is UTC

    def test_refreshed_archived_at_is_normalized_to_utc(self, sqlite_session) -> None:
        client = Client(
            nif="A1234567B",
            company_name="Acme Corp",
            contact_name="John Doe",
            email=None,
            telephone=None,
            archived_at=datetime(2026, 5, 16, 8, 0, tzinfo=UTC),
            archive_reason="duplicate",
        )
        sqlite_session.add(client)
        sqlite_session.commit()

        result = sqlite_session.get(Client, "A1234567B")

        assert result.archived_at.tzinfo is UTC
