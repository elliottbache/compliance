from compliance.db.models import (
    Certification,
    Certifier,
    Regulation,
)
from compliance.services._helpers import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    RegulationCreate,
    RegulationOut,
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


def get_regulation_by_id(
    session: Session, regulation_id: int, *, include_archived: bool = True
) -> Regulation | None:
    """Return one regulation by primary key when it is visible."""
    regulation = session.get(Regulation, regulation_id)
    return regulation if record_is_visible(regulation, include_archived) else None


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
            raise RegulationTitleConflictError(regulation.title) from exc

        raise RegulationConflictError() from exc

    return new_regulation


def post_regulation_archived_by_id(
    session: Session, regulation_id: int, *, archive_request: ArchiveRequest
) -> Regulation | None:
    """Archive a regulation by ID.

    Args:
        session: Database session used to retrieve and update the regulation.
        regulation_id: Primary key for the regulation to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The regulation ORM object, or ``None`` if no matching regulation exists.
    """
    return archive_record_by_id(session, Regulation, regulation_id, archive_request)


def post_regulation_restored_by_id(
    session: Session, regulation_id: int
) -> Regulation | None:
    """Restore an archived regulation by ID.

    Args:
        session: Database session used to retrieve and update the regulation.
        regulation_id: Primary key for the regulation to restore.

    Returns:
        The regulation ORM object, or ``None`` if no matching regulation exists.
    """
    return restore_record_by_id(session, Regulation, regulation_id)
