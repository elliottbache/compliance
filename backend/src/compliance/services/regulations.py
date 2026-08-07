"""Regulation service functions for listing, creation, archive, and restore."""

from compliance.db.models import (
    AuditAction,
    AuditTargetType,
    Certification,
    Certifier,
    Regulation,
)
from compliance.services.audit import record_audit_event
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    RegulationCreate,
    RegulationOut,
    UserOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class RegulationConflictError(Exception):
    """Raised when a regulation cannot be created because of existing data."""


class RegulationTitleConflictError(RegulationConflictError):
    """Raised when a regulation title already exists."""


def get_regulations(
    session: Session,
    *,
    certifier_id: int | None,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
) -> list[RegulationOut] | None:
    """Retrieve regulations with optional certifier filtering and pagination.

    Args:
        session: Database session used to execute the regulation query.
        certifier_id: Optional certifier ID used to restrict results to
            regulations certified by one certifier. When supplied, the
            certifier must exist.
        limit: Maximum number of regulations to return. If ``None``, all
            matching regulations are returned.
        offset: Number of regulations to skip before returning results.
        include_archived: When true, include archived regulations and, when
            filtering by certifier, archived certifier/certification links.

    Returns:
        Regulation records serialized with the public API schema, or an empty
        list if no regulations match. Returns ``None`` when ``certifier_id`` is
        supplied but no matching visible certifier exists.
    """
    stmt = select(Regulation)
    if not include_archived:
        stmt = stmt.where(Regulation.archived_at.is_(None))

    if certifier_id is not None:
        certifier = session.get(Certifier, certifier_id)
        if not record_is_visible(certifier, include_archived):
            return None
        stmt = (
            stmt.join(Regulation.regulation_certification_rel)
            .where(Certification.certifier_id == certifier_id)
            .distinct()
        )
        if not include_archived:
            stmt = stmt.where(Certification.archived_at.is_(None))

    stmt = (
        stmt.order_by(
            Regulation.published_date.desc(),
            Regulation.title,
            Regulation.id,
        )
        .limit(limit)
        .offset(offset)
    )

    regulations = session.execute(stmt).scalars().all()

    return [RegulationOut.model_validate(regulation) for regulation in regulations]


def post_new_regulation(session: Session, regulation: RegulationCreate) -> Regulation:
    """Persist a new regulation record.

    Args:
        session: Database session used to add and commit the regulation.
        regulation: Regulation creation data validated by the API layer.

    Returns:
        The created Regulation ORM object.

    Raises:
        RegulationTitleConflictError: If the regulation title already exists.
        RegulationConflictError: If another integrity conflict prevents the
            insert.
    """
    regulation_dict = regulation.model_dump()
    new_regulation = Regulation(**regulation_dict)
    try:
        session.add(new_regulation)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "uq_regulations_title":
            raise RegulationTitleConflictError(
                f"Regulation with title {regulation.title} already exists."
            ) from exc

        raise RegulationConflictError(
            f"Regulation was not added: {regulation}."
        ) from exc

    return new_regulation


def post_regulation_archived_by_id(
    session: Session,
    regulation_id: int,
    *,
    archive_request: ArchiveRequest,
    actor: UserOut | None = None,
) -> Regulation | None:
    """Archive a regulation by ID.

    Args:
        session: Database session used to retrieve and update the regulation.
        regulation_id: Primary key for the regulation to archive.
        archive_request: Archive metadata containing an optional reason.
        actor: Optional authenticated user responsible for the archive action.
            When provided, a ``record.archived`` audit event is written in the
            same transaction.

    Returns:
        The regulation ORM object, or ``None`` if no matching regulation exists.

    Side effects:
        Archives the regulation, records ``record.archived`` when ``actor`` is
        provided, and commits the session when the regulation changes.
    """
    result = archive_record_by_id(session, Regulation, regulation_id, archive_request)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_ARCHIVED,
                target_type=AuditTargetType.RECORD,
                target_id=regulation_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={
                    "record_type": "regulation",
                    "regulation_id": regulation_id,
                    "archive_reason": result.record.archive_reason,
                },
            )
        session.commit()

    return result.record


def post_regulation_restored_by_id(
    session: Session, regulation_id: int, *, actor: UserOut | None = None
) -> Regulation | None:
    """Restore an archived regulation by ID.

    Args:
        session: Database session used to retrieve and update the regulation.
        regulation_id: Primary key for the regulation to restore.
        actor: Optional authenticated user responsible for the restore action.
            When provided, a ``record.restored`` audit event is written in the
            same transaction.

    Returns:
        The regulation ORM object, or ``None`` if no matching regulation exists.

    Side effects:
        Restores the regulation, records ``record.restored`` when ``actor`` is
        provided, and commits the session when the regulation changes.
    """
    result = restore_record_by_id(session, Regulation, regulation_id)
    if result.record is None:
        return None

    if result.changed:
        if actor is not None:
            record_audit_event(
                session,
                action=AuditAction.RECORD_RESTORED,
                target_type=AuditTargetType.RECORD,
                target_id=regulation_id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                context={"record_type": "regulation", "regulation_id": regulation_id},
            )
        session.commit()

    return result.record
