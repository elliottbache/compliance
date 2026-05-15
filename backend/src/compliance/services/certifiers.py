from compliance.db.models import (
    Certifier,
)
from compliance.services._helpers import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    CertifierCreate,
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


def get_certifier_by_id(
    session: Session, certifier_id: int, *, include_archived: bool = True
) -> Certifier | None:
    """Retrieve one certifier by ID.

    Args:
        session: Database session used to retrieve the certifier.
        certifier_id: Primary key for the certifier.
        include_archived: When true, return archived certifiers.

    Returns:
        Certifier ORM object, or ``None`` if no matching visible certifier exists.
    """
    certifier = session.get(Certifier, certifier_id)
    return certifier if record_is_visible(certifier, include_archived) else None


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
                certifier.organization_name
            ) from exc

        raise CertifierConflictError() from exc

    return new_certifier


def post_certifier_archived_by_id(
    session: Session, certifier_id: int, *, archive_request: ArchiveRequest
) -> Certifier | None:
    """Archive a certifier by ID.

    Args:
        session: Database session used to retrieve and update the certifier.
        certifier_id: Primary key for the certifier to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The certifier ORM object, or ``None`` if no matching certifier exists.
    """
    return archive_record_by_id(session, Certifier, certifier_id, archive_request)


def post_certifier_restored_by_id(
    session: Session, certifier_id: int
) -> Certifier | None:
    """Restore an archived certifier by ID.

    Args:
        session: Database session used to retrieve and update the certifier.
        certifier_id: Primary key for the certifier to restore.

    Returns:
        The certifier ORM object, or ``None`` if no matching certifier exists.
    """
    return restore_record_by_id(session, Certifier, certifier_id)
