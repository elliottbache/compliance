"""Certifier service functions for listing, creation, archive, and restore."""

from compliance.db.models import (
    AuditAction,
    AuditTargetType,
    Certifier,
)
from compliance.services.audit import record_audit_event
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    CertifierCreate,
    UserOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class CertifierConflictError(Exception):
    """Raised when a certifier cannot be created because of existing data."""


class CertifierOrganizationNameConflictError(CertifierConflictError):
    """Raised when a certifier organization name already exists."""


def get_certifiers(
    session: Session, *, limit: int | None, offset: int, include_archived: bool = False
) -> list[Certifier]:
    """Retrieve certifiers ordered by organization name and ID.

    Args:
        session: Database session used to execute the certifier query.
        limit: Maximum number of certifiers to return. If ``None``, all
            certifiers are returned.
        offset: Number of certifiers to skip before returning results.
        include_archived: When true, include archived certifiers in addition to active certifiers.

    Returns:
        Certifier ORM objects, or an empty list if no certifiers exist.
    """
    stmt = select(Certifier)
    if not include_archived:
        stmt = stmt.where(Certifier.archived_at.is_(None))

    stmt = (
        stmt.order_by(Certifier.organization_name, Certifier.id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(stmt).scalars().all())


def post_new_certifier(session: Session, certifier: CertifierCreate) -> Certifier:
    """Persist a new certifier record.

    Args:
        session: Database session used to add and commit the certifier.
        certifier: Certifier data validated by the API layer.

    Returns:
        The created Certifier ORM object.

    Raises:
        CertifierOrganizationNameConflictError: If the organization name
            already exists.
        CertifierConflictError: If another integrity conflict prevents the
            insert.
    """
    certifier_dict = certifier.model_dump()
    new_certifier = Certifier(**certifier_dict)
    try:
        session.add(new_certifier)
        session.commit()

    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "uq_certifiers_organization_name":
            raise CertifierOrganizationNameConflictError(
                "Certifier with organization name "
                f"{certifier.organization_name} already exists."
            ) from exc

        raise CertifierConflictError(
            "Certifier was not added because of a data conflict."
        ) from exc

    return new_certifier


def post_certifier_archived_by_id(
    session: Session,
    certifier_id: int,
    *,
    archive_request: ArchiveRequest,
    actor: UserOut | None = None,
) -> Certifier | None:
    """Archive a certifier by ID.

    Args:
        session: Database session used to retrieve and update the certifier.
        certifier_id: Primary key for the certifier to archive.
        archive_request: Archive metadata containing an optional reason.
        actor: Optional authenticated user responsible for the archive action.
            When provided, a ``record.archived`` audit event is written in the
            same transaction.

    Returns:
        The certifier ORM object, or ``None`` if no matching certifier exists.

    Side effects:
        Archives the certifier, records ``record.archived`` when ``actor`` is
        provided, and commits the session when the certifier changes.
    """
    result = archive_record_by_id(session, Certifier, certifier_id, archive_request)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_ARCHIVED,
                target_type=AuditTargetType.RECORD,
                target_id=certifier_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={
                    "record_type": "certifier",
                    "certifier_id": certifier_id,
                    "archive_reason": result.record.archive_reason,
                },
            )
        session.commit()

    return result.record


def post_certifier_restored_by_id(
    session: Session, certifier_id: int, *, actor: UserOut | None = None
) -> Certifier | None:
    """Restore an archived certifier by ID.

    Args:
        session: Database session used to retrieve and update the certifier.
        certifier_id: Primary key for the certifier to restore.
        actor: Optional authenticated user responsible for the restore action.
            When provided, a ``record.restored`` audit event is written in the
            same transaction.

    Returns:
        The certifier ORM object, or ``None`` if no matching certifier exists.

    Side effects:
        Restores the certifier, records ``record.restored`` when ``actor`` is
        provided, and commits the session when the certifier changes.
    """
    result = restore_record_by_id(session, Certifier, certifier_id)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_RESTORED,
                target_type=AuditTargetType.RECORD,
                target_id=certifier_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={"record_type": "certifier", "certifier_id": certifier_id},
            )
        session.commit()

    return result.record
