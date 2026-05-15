from compliance.db.models import FindingAttachment


def test_finding_attachments_primary_key_excludes_certification_id() -> None:
    pk_columns = {
        column.name for column in FindingAttachment.__table__.primary_key.columns
    }

    assert pk_columns == {"finding_id", "attachment_id"}
