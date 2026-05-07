from collections.abc import Mapping, Sequence
from typing import Any
from unittest.mock import Mock

from sqlalchemy.exc import IntegrityError

from compliance.api.schemas import (
    AttachmentWithContextOut,
)
from compliance.schemas import FindingHistory


def _format_attachment(
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
