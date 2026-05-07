from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    RegulationCreate,
    RegulationOut,
)
from compliance.db.models import (
    Certification,
    Certifier,
    Regulation,
)
from compliance.services._helpers import get_constraint_name, record_is_visible


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
            filtering by certifier, archived certification links.

    Returns:
        Regulation records serialized with the public API schema, or an empty
        list if no regulations match. Returns ``None`` when ``certifier_id`` is
        supplied but no matching certifier exists.
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
    regulation_id: int, session: Session, *, include_archived: bool = False
) -> Regulation | None:
    """Return one regulation by primary key, or None when it does not exist."""
    regulation = session.get(Regulation, regulation_id)
    return regulation if record_is_visible(regulation, include_archived) else None


def post_new_regulation(regulation: RegulationCreate, session: Session) -> Regulation:
    """Persist a new regulation record.

    Args:
        regulation: Regulation creation data validated by the API layer.
        session: Database session used to add and commit the regulation.

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

        if constraint_name == "uq_title":
            raise RegulationTitleConflictError(regulation.title) from exc

        raise RegulationConflictError() from exc

    return new_regulation
