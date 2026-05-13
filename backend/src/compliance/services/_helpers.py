from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

from compliance.api.schemas import (
    ArchiveRequest,
    AttachmentWithContextOut,
)
from compliance.db.models import (
    Certification,
    Certifier,
    Client,
    Regulation,
    Site,
)
from compliance.schemas import FindingHistory
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def format_attachment(
    rows: Sequence[Mapping],
) -> AttachmentWithContextOut:
    """Aggregate query rows for a single attachment into an attachment response.

    Args:
        rows: Rows for one attachment containing attachment, certification,
            regulation, finding-link, finding, and rule objects.

    Returns:
        A single attachment response with linked findings collected under
        ``finding_links``.
    """
    attachment_dict: dict[str, Any] = dict()
    for row in rows:
        attachment_id = row["Attachment"].id
        if not attachment_dict:
            attachment_dict = {
                "id": attachment_id,
                "file_type": row["Attachment"].file_type,
                "file_path": row["Attachment"].file_path,
                "description": row["Attachment"].description,
                "uploaded_at": row["Attachment"].uploaded_at,
                "archived_at": row["Attachment"].archived_at,
                "archive_reason": row["Attachment"].archive_reason,
                "certification_id": row["Attachment"].certification_id,
                "inspection_date": row["Certification"].inspection_date,
                "regulation_id": row["Certification"].regulation_id,
                "regulation_title": row["Regulation"].title,
                "finding_links": [],
            }

        if row["Finding"] is not None:
            attachment_dict["finding_links"].append(
                _build_finding_history_from_site_attachments(row)
            )

    return AttachmentWithContextOut(**attachment_dict)


def get_constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def record_is_visible(record: Any, include_archived: bool) -> bool:
    """Return whether a record should be visible for archive-aware reads."""
    if record is None:
        return False

    archived_at = getattr(record, "archived_at", None)
    if isinstance(archived_at, Mock):
        archived_at = None

    return include_archived or archived_at is None


def archive_record_by_id(
    session: Session, model: type[Any], record_id: Any, archive_request: ArchiveRequest
) -> Any | None:
    """Archive one ORM record by primary key.

    Args:
        session: Database session used to retrieve and update the record.
        model: SQLAlchemy ORM model class to retrieve.
        record_id: Primary-key value for the record.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The ORM record, or ``None`` when no record exists for the primary key.

    Side effects:
        Sets ``archived_at`` to the current UTC time, stores a stripped archive
        reason when provided, and commits the session. Already archived records
        are returned unchanged.
    """
    record = session.get(model, record_id)
    if record is None:
        return None

    if record.archived_at is None:
        record.archived_at = datetime.now(UTC)
        archive_reason = archive_request.archive_reason
        record.archive_reason = (
            archive_reason.strip() or None if archive_reason else None
        )
        session.commit()

    return record


def restore_record_by_id(
    session: Session, model: type[Any], record_id: Any
) -> Any | None:
    """Restore one archived ORM record by primary key.

    Args:
        session: Database session used to retrieve and update the record.
        model: SQLAlchemy ORM model class to retrieve.
        record_id: Primary-key value for the record.

    Returns:
        The ORM record, or ``None`` when no record exists for the primary key.

    Side effects:
        Clears ``archived_at`` and ``archive_reason`` and commits the session
        when the record is currently archived. Active records are returned
        unchanged.
    """
    record = session.get(model, record_id)
    if record is None:
        return None

    if record.archived_at is not None:
        record.archived_at = None
        record.archive_reason = None
        session.commit()

    return record


def certification_parent_chain_is_visible(
    session: Session,
    certification: Certification,
) -> bool:
    site = session.get(Site, certification.site_id)
    if site is None or not record_is_visible(site, include_archived=False):
        return False

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived=False):
        return False

    certifier = session.get(Certifier, certification.certifier_id)
    if not record_is_visible(certifier, include_archived=False):
        return False

    regulation = session.get(Regulation, certification.regulation_id)
    return record_is_visible(regulation, include_archived=False)


def _build_finding_history_from_site_attachments(row: Mapping) -> FindingHistory:
    """Build finding history from a site-attachments query row."""
    field_sources = {
        "finding_id": ("Finding", "id"),
        "finding": ("Finding", "finding"),
        "rule_index": ("Rule", "rule_index"),
        "rule_title": ("Rule", "title"),
        "rule_description": ("Rule", "description"),
    }
    missing_keys = [
        field_name
        for field_name, (row_key, attr_name) in field_sources.items()
        if row_key not in row or not hasattr(row[row_key], attr_name)
    ]
    if missing_keys:
        raise KeyError(
            "Missing finding history fields in site attachment row: "
            f"{missing_keys}. Row keys: {sorted(row.keys())}"
        )

    finding_history = {
        field_name: getattr(row[row_key], attr_name)
        for field_name, (row_key, attr_name) in field_sources.items()
    }
    return FindingHistory.model_validate(finding_history)
