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
