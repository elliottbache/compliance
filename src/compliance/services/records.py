import logging
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
    FindingOut,
)
from compliance.db.models import (
    Attachment,
    Certification,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
)
from compliance.services._helpers import _format_attachment

logger = logging.getLogger(__name__)


class AttachmentCreateError(Exception):
    """Base error for attachment creation failures."""


class AttachmentCertificationNotFoundError(AttachmentCreateError):
    """Raised when an attachment's certification does not exist."""


class AttachmentFindingNotFoundError(AttachmentCreateError):
    """Raised when an attachment's linked finding does not exist."""


class AttachmentFindingCertificationMismatchError(AttachmentCreateError):
    """Raised when a linked finding belongs to another certification."""


class AttachmentConflictError(AttachmentCreateError):
    """Raised when attachment creation conflicts with stored data."""


def get_findings(
    session: Session, site_id: int | None, rule_id: int | None, open_only: bool
) -> list[FindingOut]:
    """Retrieve findings with optional site, rule, and open-status filters.

    Args:
        session: Database session used to execute the finding query.
        site_id: Optional site identifier used to limit findings to one site.
        rule_id: Optional rule identifier used to limit findings to one rule.
        open_only: When true, only return findings whose certification has no
            resolution date.

    Returns:
        Finding records serialized with certification, regulation, and rule
        context, or an empty list if no matching findings exist.
    """
    stmt = (
        select(
            Finding,
            Certification,
            Regulation,
            Rule,
        )
        .join(Finding.finding_certification_rel)
        .join(Certification.certification_regulation_rel)
        .join(Finding.finding_rule_rel)
    )
    if site_id is not None:
        stmt = stmt.where(Certification.site_id == site_id)
    if rule_id is not None:
        stmt = stmt.where(Rule.id == rule_id)
    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    results = session.execute(stmt).mappings().all()

    return _format_findings(results)


def get_attachment_by_id(
    attachment_id: int, session: Session
) -> AttachmentWithContextOut | None:
    """Retrieve one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier of the attachment to retrieve.
        session: Database session used to execute the attachment query.

    Returns:
        A formatted attachment response containing certification, regulation,
        and linked finding context, or ``None`` if no matching attachment exists.
    """
    stmt = (
        select(
            Attachment,
            Certification,
            Regulation,
            FindingAttachment,
            Finding,
            Rule,
        )
        .where(Attachment.id == attachment_id)
        .join(Attachment.attachment_certification_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(Attachment.attachment_finding_attachment_rel)
        .outerjoin(FindingAttachment.finding_attachment_finding_rel)
        .outerjoin(Finding.finding_rule_rel)
    )
    rows = session.execute(stmt).mappings().all()
    return None if not rows else _format_attachment(rows)


def post_new_attachment(
    attachment: AttachmentCreate, session: Session
) -> AttachmentOut:
    """Persist a new attachment metadata record and optional finding links.

    Builds temporary storage metadata for the attachment, validates that the
    parent certification and requested linked findings exist, and creates any
    finding-attachment link rows in the same transaction.

    Args:
        attachment: Attachment metadata validated by the API layer.
        session: Database session used to validate related records and persist
            the attachment metadata.

    Returns:
        The created attachment metadata with certification and regulation
        context.

    Raises:
        AttachmentCertificationNotFoundError: If the parent certification does
            not exist.
        AttachmentFindingNotFoundError: If a requested linked finding does not
            exist.
        AttachmentFindingCertificationMismatchError: If a requested finding
            belongs to another certification.
        AttachmentConflictError: If the attachment or link rows conflict with
            existing stored data.
    """
    attachment_dict = attachment.model_dump()
    orm_data = {
        "file_type": attachment.file_type,
        "certification_id": attachment.certification_id,
        "description": attachment.description,
        "file_path": "/path/placeholder/"
        + attachment_dict["file_name"]
        + "."
        + attachment_dict["file_type"],
        "uploaded_at": date.today(),
    }
    new_attachment = Attachment(**orm_data)

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if findings exist
    for finding_id in attachment.finding_ids:
        finding = session.get(Finding, finding_id)
        if finding is None:
            raise AttachmentFindingNotFoundError(
                f"Finding {finding_id} does not exist."
            )

        if finding.certification_id != attachment.certification_id:
            raise AttachmentFindingCertificationMismatchError(
                f"Finding {finding_id} does not belong to certification "
                f"{attachment.certification_id}."
            )

    try:
        # add new attachment
        session.add(new_attachment)
        session.flush()

        # add new findingAttachment
        for finding_id in attachment.finding_ids:
            new_finding_attachment = FindingAttachment(
                finding_id=finding_id,
                attachment_id=new_attachment.id,
                certification_id=attachment.certification_id,
            )
            session.add(new_finding_attachment)
        session.flush()

        new_attachment_with_context = _format_new_attachment_with_context(
            new_attachment,
            certification,
            attachment.finding_ids,
        )
        session.commit()

    except IntegrityError as e:
        logger.warning(f"Error posting new attachment: {e}")
        session.rollback()
        raise AttachmentConflictError("Attachment could not be created.") from e

    except Exception:
        session.rollback()
        raise

    return AttachmentOut.model_validate(new_attachment_with_context)


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
    file_name = Path(attachment.file_path).stem
    return AttachmentOut(
        id=attachment.id,
        file_type=attachment.file_type,
        certification_id=attachment.certification_id,
        description=attachment.description,
        uploaded_at=attachment.uploaded_at,
        file_name=file_name,
        finding_ids=list(finding_ids),
        inspection_date=certification.inspection_date,
        regulation_id=certification.regulation_id,
        regulation_title=certification.certification_regulation_rel.title,
    )


def _format_findings(finding_list: Sequence[Mapping]) -> list[FindingOut]:
    """Format finding query rows into public finding output records.

    Args:
        finding_list: Rows containing ``Finding``, ``Certification``,
            ``Regulation``, and ``Rule`` ORM objects.

    Returns:
        Finding records serialized with certification and rule context.

    Raises:
        KeyError: If required row objects or nested fields are missing.
    """
    return [_build_finding_out(row) for row in finding_list]


def _build_finding_out(row: Mapping) -> FindingOut:
    """Build a public finding output object from one finding query row."""
    field_sources = {
        "finding_id": ("Finding", "id"),
        "finding": ("Finding", "finding"),
        "site_id": ("Certification", "site_id"),
        "certification_id": ("Certification", "id"),
        "certification_resolution_date": ("Certification", "resolution_date"),
        "certification_title": ("Regulation", "title"),
        "rule_id": ("Rule", "id"),
        "rule_index": ("Rule", "rule_index"),
        "rule_title": ("Rule", "title"),
        "rule_description": ("Rule", "description"),
    }
    missing_fields = [
        field_name
        for field_name, (row_key, attr_name) in field_sources.items()
        if row_key not in row or not hasattr(row[row_key], attr_name)
    ]
    if missing_fields:
        raise KeyError(
            "Missing finding output fields in row: "
            f"{missing_fields}. Row keys: {sorted(row.keys())}"
        )

    finding_out = {
        field_name: getattr(row[row_key], attr_name)
        for field_name, (row_key, attr_name) in field_sources.items()
    }

    return FindingOut.model_validate(finding_out)
