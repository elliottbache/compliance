from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    CertifierCreate,
    CertifierOut,
)
from compliance.db.models import (
    Certifier,
)
from compliance.services._helpers import get_constraint_name


class CertifierConflictError(Exception):
    """Raised when a certifier cannot be created because of existing data."""


class CertifierOrganizationNameConflictError(CertifierConflictError):
    """Raised when a certifier organization name already exists."""


def get_certifiers(
    session: Session, limit: int | None, offset: int
) -> list[CertifierOut]:
    """Retrieve certifiers ordered by organization name and ID.

    Args:
        session: Database session used to execute the certifier query.
        limit: Maximum number of certifiers to return. If ``None``, all
            certifiers are returned.
        offset: Number of certifiers to skip before returning results.

    Returns:
        Certifier records serialized with the public API schema, or an empty
        list if no certifiers exist.
    """
    stmt = (
        select(Certifier)
        .order_by(Certifier.organization_name, Certifier.id)
        .limit(limit)
        .offset(offset)
    )
    certifiers = session.execute(stmt).scalars().all()

    return [CertifierOut.model_validate(certifier) for certifier in certifiers]


def get_certifier_by_id(certifier_id: int, session: Session) -> CertifierOut | None:
    """Retrieve one certifier by ID.

    Args:
        certifier_id: Primary key for the certifier.
        session: Database session used to retrieve the certifier.

    Returns:
        Certifier record serialized with the public API schema, or ``None`` if
        no matching certifier exists.
    """
    certifier_db = session.get(Certifier, certifier_id)

    return None if not certifier_db else CertifierOut.model_validate(certifier_db)


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
