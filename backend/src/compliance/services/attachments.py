import shutil
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from compliance.api.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from compliance.db.models import (
    Attachment,
    Certification,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.services._helpers import (
    archive_record_by_id,
    format_attachment,
    record_is_visible,
    restore_record_by_id,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_UPLOAD_DIR = Path(
    "backend/storage/attachments"
)  # we should already be in backend folder of repo
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv"}
_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
    "text/csv",
}
_ALLOWED_SIZE = int(5e7)


class AttachmentCreateError(Exception):
    """Base error for attachment creation failures."""


class AttachmentNotFoundError(AttachmentCreateError):
    """Raised when an attachment ID doesn't exist."""


class AttachmentSiteNotFoundError(AttachmentCreateError):
    """Raised when an attachment filter references a missing site."""


class AttachmentCertificationNotFoundError(AttachmentCreateError):
    """Raised when an attachment's certification does not exist."""


class AttachmentRuleNotFoundError(AttachmentCreateError):
    """Raised when an attachment filter references a missing rule."""


class AttachmentFindingNotFoundError(AttachmentCreateError):
    """Raised when an attachment's linked finding does not exist."""


class AttachmentFindingCertificationMismatchError(AttachmentCreateError):
    """Raised when a linked finding belongs to another certification."""


class AttachmentConflictError(AttachmentCreateError):
    """Raised when attachment creation conflicts with stored data."""


class AttachmentFileError(AttachmentCreateError):
    """Raised when attachment file upload is invalid."""


def get_attachments(
    session: Session,
    *,
    site_id: int | None,
    certification_id: int | None,
    rule_id: int | None,
    finding_id: int | None,
    include_archived: bool = False,
) -> list[AttachmentOut]:
    """Retrieve attachments with optional filters and linked finding context.

    Args:
        session: Database session used to execute the attachment query.
        site_id: Optional site identifier used to limit attachment to one site.
        certification_id: Optional certification identifier used to limit attachments
            to one certification.
        rule_id: Optional rule identifier used to limit attachments to one rule.
        finding_id: Optional finding identifier used to limit attachments to one
            finding.
        include_archived: When true, include archived attachments and related
            certification, site, regulation, rule, and finding context in the
            results. By default, archived finding and rule rows are omitted from
            optional context without hiding otherwise visible attachments.

    Returns:
        Attachment records serialized with visible certification, regulation,
        and optional finding context. Returns an empty list if no matching
        visible attachments exist.

    Raises:
        AttachmentSiteNotFoundError: If ``site_id`` is provided but no visible
            site exists.
        AttachmentCertificationNotFoundError: If ``certification_id`` is
            provided but no visible certification exists.
        AttachmentRuleNotFoundError: If ``rule_id`` is provided but no visible
            rule exists.
        AttachmentFindingNotFoundError: If ``finding_id`` is provided but no
            visible finding exists.
    """
    finding_join_condition = (Finding.id == FindingAttachment.finding_id) & (
        Finding.certification_id == FindingAttachment.certification_id
    )
    rule_join_condition = Rule.id == Finding.rule_id
    if not include_archived:
        finding_join_condition = finding_join_condition & Finding.archived_at.is_(None)
        rule_join_condition = rule_join_condition & Rule.archived_at.is_(None)

    stmt = (
        select(Attachment, Certification, Regulation, FindingAttachment, Finding, Rule)
        .join(Attachment.attachment_certification_rel)
        .join(Certification.certification_site_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(
            FindingAttachment,
            (FindingAttachment.attachment_id == Attachment.id)
            & (FindingAttachment.certification_id == Attachment.certification_id),
        )
        .outerjoin(
            Finding,
            finding_join_condition,
        )
        .outerjoin(Rule, rule_join_condition)
    )
    if not include_archived:
        stmt = stmt.where(Attachment.archived_at.is_(None))
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    if site_id is not None:
        site = session.get(Site, site_id)
        if not record_is_visible(site, include_archived):
            raise AttachmentSiteNotFoundError(site_id)
        stmt = stmt.where(Certification.site_id == site_id)

    if certification_id is not None:
        certification = session.get(Certification, certification_id)
        if not record_is_visible(certification, include_archived):
            raise AttachmentCertificationNotFoundError(certification_id)
        stmt = stmt.where(Certification.id == certification_id)

    if rule_id is not None:
        rule = session.get(Rule, rule_id)
        if not record_is_visible(rule, include_archived):
            raise AttachmentRuleNotFoundError(rule_id)
        stmt = stmt.where(Rule.id == rule_id)

    if finding_id is not None:
        finding = session.get(Finding, finding_id)
        if not record_is_visible(finding, include_archived):
            raise AttachmentFindingNotFoundError(finding_id)
        stmt = stmt.where(FindingAttachment.finding_id == finding_id)

    stmt = stmt.order_by(Attachment.id, Finding.id)

    results = session.execute(stmt).mappings().all()

    return _format_attachments(results)


def get_attachment_by_id(
    session: Session, attachment_id: int, *, include_archived: bool = True
) -> AttachmentWithContextOut | None:
    """Retrieve one attachment with certification, regulation, and finding context.

    Args:
        session: Database session used to execute the attachment query.
        attachment_id: Unique identifier of the attachment to retrieve.
        include_archived: When true, return archived attachments and related
            certification, site, regulation, rule, and finding context. By
            default, archived finding and rule rows are omitted from optional
            context without hiding an otherwise visible attachment.

    Returns:
        A formatted attachment response containing visible certification,
        regulation, and optional linked finding context, or ``None`` if no
        matching visible attachment exists.
    """
    finding_join_condition = (Finding.id == FindingAttachment.finding_id) & (
        Finding.certification_id == FindingAttachment.certification_id
    )
    rule_join_condition = Rule.id == Finding.rule_id
    if not include_archived:
        finding_join_condition = finding_join_condition & Finding.archived_at.is_(None)
        rule_join_condition = rule_join_condition & Rule.archived_at.is_(None)

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
        .join(Certification.certification_site_rel)
        .join(Certification.certification_regulation_rel)
        .outerjoin(
            FindingAttachment,
            (FindingAttachment.attachment_id == Attachment.id)
            & (FindingAttachment.certification_id == Attachment.certification_id),
        )
        .outerjoin(Finding, finding_join_condition)
        .outerjoin(Rule, rule_join_condition)
    )
    if not include_archived:
        stmt = stmt.where(Attachment.archived_at.is_(None))
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    rows = session.execute(stmt).mappings().all()
    return None if not rows else format_attachment(rows)


def get_attachment_download(session: Session, attachment_id: int) -> tuple[str, Path]:
    attachment = session.get(Attachment, attachment_id)
    if not attachment:
        raise AttachmentNotFoundError(attachment_id)

    if not attachment.file_path:
        raise AttachmentFileError(attachment_id, attachment.file_path)

    file_path = Path(attachment.file_path)
    if not file_path.is_file():
        raise AttachmentFileError(attachment_id, attachment.file_path)

    file_name = attachment.file_name or ""
    file_name += str(file_path.suffix)

    return file_name, file_path


def post_new_attachment(
    session: Session, attachment: AttachmentCreate
) -> AttachmentOut:
    """Persist a new attachment metadata record and optional finding links.

    Builds temporary storage metadata for the attachment, validates that the
    parent certification and requested linked findings exist, and creates any
    finding-attachment link rows in the same transaction.

    Args:
        session: Database session used to validate related records and persist
            the attachment metadata.
        attachment: Attachment metadata validated by the API layer.

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
    orm_data = {
        "file_name": attachment.file_name,
        "certification_id": attachment.certification_id,
        "description": attachment.description,
        "file_path": f"/path/placeholder/{attachment.file_name}",
        "uploaded_at": None,
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
        session.rollback()
        print(f"e: {e}")
        raise AttachmentConflictError("Attachment could not be created.") from e

    except Exception:
        session.rollback()
        raise

    return AttachmentOut.model_validate(new_attachment_with_context)


def post_attachment_upload(
    session: Session,
    *,
    attachment_id: int,
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    file_stream: BinaryIO,
) -> Attachment:
    # check that content type and extension is acceptable
    if not _validate_file_size_type_and_ext(file_size, file_type, file_name):
        raise AttachmentFileError(file_size, file_type, file_name)

    # fetch metadata
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise AttachmentNotFoundError(attachment_id)

    # extract extension
    ext = Path(file_name).suffix if file_name is not None else ""

    # create file name
    unique_filename = f"{uuid4()}{ext}"

    # set file path
    file_path = _UPLOAD_DIR / unique_filename

    try:
        # stream to path
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_stream, buffer)

        attachment.file_path = str(file_path)
        attachment.uploaded_at = datetime.now(UTC)

        session.add(attachment)
        session.commit()
        session.refresh(attachment)

    except Exception as e:
        session.rollback()
        file_path.unlink(missing_ok=True)
        raise AttachmentConflictError(file_path) from e

    return attachment


def post_attachment_archived_by_id(
    session: Session, attachment_id: int, *, archive_request: ArchiveRequest
) -> AttachmentWithContextOut | None:
    """Archive an attachment by ID.

    Args:
        session: Database session used to retrieve and update the attachment.
        attachment_id: Primary key for the attachment to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The archived attachment with context, or ``None`` if no matching
        attachment exists.
    """
    attachment = archive_record_by_id(
        session, Attachment, attachment_id, archive_request
    )
    if attachment is None:
        return None
    return get_attachment_by_id(session, attachment_id, include_archived=True)


def post_attachment_restored_by_id(
    session: Session, attachment_id: int
) -> AttachmentWithContextOut | None:
    """Restore an archived attachment by ID.

    Args:
        session: Database session used to retrieve and update the attachment.
        attachment_id: Primary key for the attachment to restore.

    Returns:
        The restored attachment with context, or ``None`` if no matching
        attachment exists.
    """
    attachment = restore_record_by_id(session, Attachment, attachment_id)
    if attachment is None:
        return None
    return get_attachment_by_id(session, attachment_id, include_archived=True)


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


def _validate_file_size_type_and_ext(
    file_size: int | None,
    file_type: str | None,
    file_name: str | None,
    *,
    allowed_size: int = _ALLOWED_SIZE,
    allowed_types: set[str] = _ALLOWED_MIME_TYPES,
    allowed_extensions: set[str] = _ALLOWED_EXTENSIONS,
) -> bool:

    if not file_size or file_size > allowed_size:
        return False

    if file_type is None or file_type not in allowed_types:
        return False

    return file_name is None or Path(file_name).suffix in allowed_extensions


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
