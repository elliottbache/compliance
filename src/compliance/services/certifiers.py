from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    CertifierCreate,
)
from compliance.db.models import (
    Certifier,
)
from compliance.services._helpers import get_constraint_name, record_is_visible


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


def get_certifier_by_id(
    certifier_id: int, session: Session, *, include_archived: bool = False
) -> Certifier | None:
    """Retrieve one certifier by ID.

    Args:
        certifier_id: Primary key for the certifier.
        session: Database session used to retrieve the certifier.
        include_archived: When true, return archived certifiers.

    Returns:
        Certifier ORM object, or ``None`` if no matching visible certifier exists.
    """
    certifier = session.get(Certifier, certifier_id)
    return certifier if record_is_visible(certifier, include_archived) else None


def post_new_certifier(certifier: CertifierCreate, session: Session) -> Certifier:
    """Persist a new certifier record.

    Args:
        certifier: Certifier data validated by the API layer.
        session: Database session used to add and commit the certifier.

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

        if constraint_name == "uq_organization_name":
            raise CertifierOrganizationNameConflictError(
                certifier.organization_name
            ) from exc

        raise CertifierConflictError() from exc

    return new_certifier
