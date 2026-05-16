from collections.abc import Mapping, Sequence
from typing import Any

from compliance.db.models import Attachment, Certification
from compliance.schemas import FindingHistory
from compliance.services.schemas import AttachmentOut, AttachmentWithContextOut


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
                "file_name": row["Attachment"].file_name,
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


def _format_new_attachment_with_context(
    attachment: Attachment,
    certification: Certification,
    finding_ids: list[int],
) -> AttachmentOut:
    """Build output metadata for a newly created attachment.

    Args:
        attachment: Newly persisted attachment ORM object.
        certification: Parent certification for the attachment.
        finding_ids: Finding IDs linked to the attachment during creation.

    Returns:
        Attachment metadata enriched with certification and regulation context.
    """
    return AttachmentOut(
        id=attachment.id,
        file_name=attachment.file_name,
        file_path=attachment.file_path,
        certification_id=attachment.certification_id,
        description=attachment.description,
        uploaded_at=None,
        finding_ids=list(finding_ids),
        inspection_date=certification.inspection_date,
        regulation_id=certification.regulation_id,
        regulation_title=certification.certification_regulation_rel.title,
        archived_at=attachment.archived_at,
        archive_reason=attachment.archive_reason,
    )


def _format_attachments(attachment_list: Sequence[Mapping]) -> list[AttachmentOut]:
    """Format attachment query rows into public attachment output records."""
    rows_by_attachment: dict[int, list[Mapping]] = {}
    for row in attachment_list:
        attachment_id = row["Attachment"].id
        if attachment_id not in rows_by_attachment:
            rows_by_attachment[attachment_id] = []
        rows_by_attachment[attachment_id].append(row)

    return [_build_attachment_out(rows) for rows in rows_by_attachment.values()]


def _build_attachment_out(rows: Sequence[Mapping]) -> AttachmentOut:
    """Build one attachment output object from grouped attachment query rows."""
    first_row = rows[0]
    attachment = first_row["Attachment"]
    certification = first_row["Certification"]
    regulation = first_row["Regulation"]

    finding_ids: list[int] = []
    for row in rows:
        finding = row["Finding"]
        if finding is not None and finding.id not in finding_ids:
            finding_ids.append(finding.id)

    return AttachmentOut(
        id=attachment.id,
        file_name=attachment.file_name,
        file_path=attachment.file_path,
        certification_id=attachment.certification_id,
        description=attachment.description,
        finding_ids=finding_ids,
        uploaded_at=attachment.uploaded_at,
        inspection_date=certification.inspection_date,
        regulation_id=certification.regulation_id,
        regulation_title=regulation.title,
        archived_at=attachment.archived_at,
        archive_reason=attachment.archive_reason,
    )
