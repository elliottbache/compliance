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
from compliance.services._helpers import _format_attachment, record_is_visible


class AttachmentCreateError(Exception):
    """Base error for attachment creation failures."""


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
    attachment_id: int, session: Session, *, include_archived: bool = False
) -> AttachmentWithContextOut | None:
    """Retrieve one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier of the attachment to retrieve.
        session: Database session used to execute the attachment query.
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
        file_type=attachment.file_type,
        file_name=Path(attachment.file_path).stem,
        certification_id=attachment.certification_id,
        description=attachment.description,
        finding_ids=finding_ids,
        uploaded_at=attachment.uploaded_at,
        inspection_date=certification.inspection_date,
        regulation_id=certification.regulation_id,
        regulation_title=regulation.title,
    )
