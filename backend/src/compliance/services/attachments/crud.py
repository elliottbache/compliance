"""Attachment metadata queries and mutations."""

from compliance.db.models import (
    Attachment,
    Certification,
    Client,
    Finding,
    FindingAttachment,
    Regulation,
    Rule,
    Site,
)
from compliance.services.attachments.exceptions import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    AttachmentPermissionError,
    AttachmentRuleNotFoundError,
    AttachmentSiteNotFoundError,
)
from compliance.services.attachments.formatting import (
    _format_attachments,
    _format_new_attachment_with_context,
    format_attachment,
)
from compliance.services.lifecycle import (
    archive_record_by_id,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


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
        .join(Site.site_client_rel)
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
        stmt = stmt.where(Client.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    if site_id is not None:
        site = session.get(Site, site_id)
        if not record_is_visible(site, include_archived):
            raise AttachmentSiteNotFoundError(f"Missing site {site_id}.")
        stmt = stmt.where(Certification.site_id == site_id)

    if certification_id is not None:
        certification = session.get(Certification, certification_id)
        if not record_is_visible(certification, include_archived):
            raise AttachmentCertificationNotFoundError(
                f"Missing certification {certification_id}."
            )
        stmt = stmt.where(Certification.id == certification_id)

    if rule_id is not None:
        rule = session.get(Rule, rule_id)
        if not record_is_visible(rule, include_archived):
            raise AttachmentRuleNotFoundError(f"Missing rule {rule_id}.")
        stmt = stmt.where(Rule.id == rule_id)

    if finding_id is not None:
        finding = session.get(Finding, finding_id)
        if not record_is_visible(finding, include_archived):
            raise AttachmentFindingNotFoundError(f"Missing finding {finding_id}.")
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
        .join(Site.site_client_rel)
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
        stmt = stmt.where(Client.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))

    rows = session.execute(stmt).mappings().all()
    return None if not rows else format_attachment(rows)


def post_new_attachment(
    session: Session, attachment: AttachmentCreate, user_id: int
) -> AttachmentOut:
    """Persist a new attachment metadata record and optional finding links.

    Builds temporary storage metadata for the attachment, validates that the
    parent certification and requested linked findings exist, and creates any
    finding-attachment link rows in the same transaction.
    Parent validation checks existence, not visibility in default archive-aware
    reads. This allows bookkeeping entries under archived certifications or
    findings.

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
        "file_path": None,
        "uploaded_at": None,
    }
    new_attachment = Attachment(**orm_data)

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if certification belongs to current user
    if certification.inspector_id != user_id:
        raise AttachmentPermissionError(
            f"Certification {attachment.certification_id} is assigned to inspector {certification.inspector_id}.  You are logged in as inspector {user_id}."
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


def post_attachment_archived_by_id(
    session: Session,
    attachment_id: int,
    *,
    archive_request: ArchiveRequest,
    user_id: int,
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
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        return None

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if certification belongs to current user
    if certification.inspector_id != user_id:
        raise AttachmentPermissionError(
            f"Certification {attachment.certification_id} is assigned to inspector {certification.inspector_id}.  You are logged in as inspector {user_id}."
        )

    attachment = archive_record_by_id(
        session, Attachment, attachment_id, archive_request
    )
    if attachment is None:
        return None
    return get_attachment_by_id(session, attachment_id, include_archived=True)


def post_attachment_restored_by_id(
    session: Session, attachment_id: int, user_id: int
) -> AttachmentWithContextOut | None:
    """Restore an archived attachment by ID.

    Args:
        session: Database session used to retrieve and update the attachment.
        attachment_id: Primary key for the attachment to restore.

    Returns:
        The restored attachment with context, or ``None`` if no matching
        attachment exists.
    """
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        return None

    # check if certification exists
    certification = session.get(Certification, attachment.certification_id)
    if certification is None:
        raise AttachmentCertificationNotFoundError(
            f"Certification {attachment.certification_id} does not exist."
        )

    # check if certification belongs to current user
    if certification.inspector_id != user_id:
        raise AttachmentPermissionError(
            f"Certification {attachment.certification_id} is assigned to inspector {certification.inspector_id}.  You are logged in as inspector {user_id}."
        )

    attachment = restore_record_by_id(session, Attachment, attachment_id)
    if attachment is None:
        return None
    return get_attachment_by_id(session, attachment_id, include_archived=True)
