from collections.abc import Sequence

from compliance.db.models import Certification, Client, Site
from compliance.services.lifecycle import record_is_visible
from compliance.services.schemas import SiteCertificationsOut
from compliance.services.sites.crud import SiteClientNotFoundError, SiteNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session


def get_site_certifications(
    session: Session,
    site_id: int,
    *,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
) -> list[Certification]:
    """Retrieve certifications for one site ordered by latest resolution date.

    Args:
        session: Database session used to execute the certification query.
        site_id: Unique identifier of the site whose certifications should be
            retrieved.
        limit: Maximum number of certifications to return. If ``None``, all
            matching certifications are returned.
        offset: Number of matching certifications to skip before returning
            results.
        include_archived: When true, include archived site, parent client,
            and certification records.

    Returns:
        A list of visible certification ORM objects ordered by resolution date
        descending and then ID, or [] if no matching certifications exist.

    Raises:
        SiteNotFoundError if the site id doesn't correspond to any visible ID.
        SiteClientNotFoundError if the site NIF doesn't correspond to any visible NIF.
    """
    site = session.get(Site, site_id)
    if site is None or not record_is_visible(site, include_archived):
        raise SiteNotFoundError(site_id)

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived):
        raise SiteClientNotFoundError(site.nif)

    stmt = (
        select(Certification)
        .where(Certification.site_id == site_id)
        .join(Certification.certification_site_rel)
        .order_by(Certification.resolution_date.desc(), Certification.id)
        .limit(limit)
        .offset(offset)
    )
    if not include_archived:
        stmt = stmt.where(Certification.archived_at.is_(None))
        stmt = stmt.where(Site.archived_at.is_(None))

    return list(session.execute(stmt).scalars().all())


def format_site_certifications(
    site_id: int, certifications: Sequence[Certification]
) -> SiteCertificationsOut:
    """Build a site-level certification collection response.

    Args:
        site_id: Unique identifier of the site whose certifications were queried.
        certifications: Certification ORM objects returned for the site.

    Returns:
        Site certification response containing the site ID and serialized
        certification records.
    """
    return SiteCertificationsOut.model_validate(
        {"site_id": site_id, "certifications": list(certifications)}
    )
