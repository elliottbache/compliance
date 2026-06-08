import logging

from compliance.db.models import (
    Certification,
    Certifier,
    Client,
    Regulation,
    Site,
    User,
)
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    CertificationCreate,
    CertificationOut,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class CertificationConflictError(Exception):
    """Raised when a certification cannot be created because of existing data."""


class CertificationCertifierNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing certifier."""


class CertificationRegulationNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing regulation."""


class CertificationSiteNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing site."""


class CertificationInspectorNotFoundError(CertificationConflictError):
    """Raised when a certification references a missing inspector."""


class CertificationInspectorInactiveError(CertificationConflictError):
    """Raised when a certification references an inactive inspector."""


def get_certifications(
    session: Session,
    *,
    site_id: int | None,
    open_only: bool,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
    inspector_id: int | None,
) -> list[CertificationOut] | None:
    """Retrieve certifications with optional site and open-only filters.

    Args:
        session: Database session used to execute the certification query.
        site_id: Optional site ID used to restrict results to one site. When
            supplied, the site must exist.
        open_only: When true, only return certifications without a resolution
            date.
        limit: Maximum number of certifications to return. If ``None``, all
            certifications are returned.
        offset: Number of certifications to skip before returning results.
        include_archived: When true, include archived certifications and
            archived parent site, regulation, and certifier records in the
            results.
        inspector_id: Optional inspector ID used to restrict results to one inspector. When
            supplied, the inspector must exist.

    Returns:
        Certification records serialized with the public API schema for visible
        certifications whose required parents are also visible, or an empty
        list if no certifications match. Returns ``None`` when ``site_id`` is
        supplied but no matching visible site exists.
    """
    stmt = (
        select(Certification)
        .join(Certification.certification_site_rel)
        .join(Site.site_client_rel)
        .join(Certification.certification_regulation_rel)
        .join(Certification.certification_certifier_rel)
    )
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Client.archived_at.is_(None))
        stmt = stmt.where(Regulation.archived_at.is_(None))
        stmt = stmt.where(Certifier.archived_at.is_(None))

    if site_id is not None:
        site = session.get(Site, site_id)
        if not record_is_visible(site, include_archived):
            return None
        stmt = stmt.where(Certification.site_id == site_id)

    if open_only:
        stmt = stmt.where(Certification.resolution_date.is_(None))

    if inspector_id is not None:
        stmt = stmt.where(Certification.inspector_id == inspector_id)

    stmt = (
        stmt.order_by(
            Certification.regulation_id,
            Certification.inspection_date.desc(),
            Certification.id,
        )
        .limit(limit)
        .offset(offset)
    )

    certifications = session.execute(stmt).scalars().all()

    return [
        CertificationOut.model_validate(certification)
        for certification in certifications
    ]


def post_new_certification(
    session: Session, certification: CertificationCreate
) -> Certification:
    """Persist a new certification record.

    Parent validation checks that the certifier, regulation, and site exist,
    not whether they are visible in default archive-aware reads. This allows
    bookkeeping entries under archived parents.

    Args:
        session: Database session used to add and commit the certification.
        certification: Certification creation data validated by the API layer.

    Returns:
        The created Certification ORM object.

    Raises:
        CertificationCertifierNotFoundError: If the certifier ID does not exist.
        CertificationRegulationNotFoundError: If the regulation ID does not exist.
        CertificationSiteNotFoundError: If the site ID does not exist.
        CertificationInspectorNotFoundError: If the inspector ID does not exist.
        CertificationInspectorInactiveError: If the inspector is inactive.
        CertificationConflictError: If another integrity conflict prevents the insert.
    """
    certification_dict = certification.model_dump()
    new_certification = Certification(**certification_dict)

    if certification.inspector_id is not None:
        inspector = session.get(User, certification.inspector_id)
        if not inspector:
            raise CertificationInspectorNotFoundError(certification.inspector_id)
        if not inspector.is_active:
            raise CertificationInspectorInactiveError(inspector.id)

    try:
        session.add(new_certification)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "fk_certifications_certifier_id_certifiers":
            raise CertificationCertifierNotFoundError(
                certification.certifier_id
            ) from exc

        if constraint_name == "fk_certifications_regulation_id_regulations":
            raise CertificationRegulationNotFoundError(
                certification.regulation_id
            ) from exc

        if constraint_name == "fk_certifications_site_id_sites":
            raise CertificationSiteNotFoundError(certification.site_id) from exc

        if constraint_name == "fk_certifications_inspector_id_users":
            raise CertificationInspectorNotFoundError(
                certification.inspector_id
            ) from exc

        raise CertificationConflictError() from exc

    return new_certification


def post_certification_archived_by_id(
    session: Session, certification_id: int, *, archive_request: ArchiveRequest
) -> Certification | None:
    """Archive a certification by ID.

    Args:
        session: Database session used to retrieve and update the certification.
        certification_id: Primary key for the certification to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The certification ORM object, or ``None`` if no matching certification
        exists.
    """
    return archive_record_by_id(
        session, Certification, certification_id, archive_request
    )


def post_certification_restored_by_id(
    session: Session, certification_id: int
) -> Certification | None:
    """Restore an archived certification by ID.

    Args:
        session: Database session used to retrieve and update the certification.
        certification_id: Primary key for the certification to restore.

    Returns:
        The certification ORM object, or ``None`` if no matching certification
        exists.
    """
    return restore_record_by_id(session, Certification, certification_id)
