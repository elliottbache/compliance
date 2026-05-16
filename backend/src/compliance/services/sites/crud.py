from compliance.db.models import Client, Site
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    record_is_visible,
    restore_record_by_id,
)
from compliance.services.schemas import ArchiveRequest, SiteCreate
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class SiteConflictError(Exception):
    """Raised when a site cannot be created because of existing data."""


class SiteClientNotFoundError(SiteConflictError):
    """Raised when a site references a missing client."""


class SiteNotFoundError(SiteConflictError):
    """Raised when a site references a missing ID."""


def get_sites(
    session: Session,
    *,
    nif: str | None,
    limit: int | None,
    offset: int,
    include_archived: bool = False,
) -> list[Site] | None:
    """Retrieve sites with optional client filtering.

    Args:
        session: Database session used to execute the site query.
        nif: Optional client NIF used to restrict results to one client. When
            supplied, the client must exist.
        limit: Maximum number of sites to return. If ``None``, all sites
            are returned.
        offset: Number of sites to skip before returning results.
        include_archived: When true, include archived sites and archived parent
            clients in the results.

    Returns:
        Site ORM objects whose parent clients are visible, or an empty list if
        no sites match. Returns ``None`` when ``nif`` is supplied but no
        matching visible client exists.
    """
    stmt = select(Site).join(Site.site_client_rel)
    if not include_archived:
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Client.archived_at.is_(None))

    if nif is not None:
        client = session.get(Client, nif)
        if not record_is_visible(client, include_archived):
            return None
        stmt = stmt.where(Site.nif == nif)

    stmt = stmt.order_by(Site.city, Site.nif, Site.id).limit(limit).offset(offset)

    return list(session.execute(stmt).scalars().all())


def get_site_by_id(
    session: Session, site_id: int, *, include_archived: bool = True
) -> Site:
    """Return one site by primary key when it and its parent client are visible."""
    site = session.get(Site, site_id)
    if site is None or not record_is_visible(site, include_archived):
        raise SiteNotFoundError(site)

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived):
        raise SiteClientNotFoundError(client)

    stmt = select(Site).where(Site.id == site_id).join(Site.site_client_rel)
    if not include_archived:
        stmt = stmt.where(Site.archived_at.is_(None))
        stmt = stmt.where(Client.archived_at.is_(None))

    return session.execute(stmt).scalar_one()


def post_new_site(session: Session, site: SiteCreate) -> Site:
    """Persist a new site record.

    Parent validation checks that the client exists, not whether the client is
    visible in default archive-aware reads. This allows bookkeeping entries
    under archived clients.

    Args:
        session: Database session used to add and commit the site.
        site: Site creation data validated by the API layer.

    Returns:
        The created Site ORM object.

    Raises:
        SiteClientNotFoundError: If the client NIF does not exist.
        SiteConflictError: If another integrity conflict prevents the insert.
    """
    site_dict = site.model_dump()
    new_site = Site(**site_dict)
    try:
        session.add(new_site)
        session.commit()
    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "fk_sites_nif_clients":
            raise SiteClientNotFoundError(site.nif) from exc

        raise SiteConflictError() from exc

    return new_site


def post_site_archived_by_id(
    session: Session, site_id: int, *, archive_request: ArchiveRequest
) -> Site | None:
    """Archive a site by ID.

    Args:
        session: Database session used to retrieve and update the site.
        site_id: Primary key for the site to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The site ORM object, or ``None`` if no matching site exists.
    """
    return archive_record_by_id(session, Site, site_id, archive_request)


def post_site_restored_by_id(session: Session, site_id: int) -> Site | None:
    """Restore an archived site by ID.

    Args:
        session: Database session used to retrieve and update the site.
        site_id: Primary key for the site to restore.

    Returns:
        The site ORM object, or ``None`` if no matching site exists.
    """
    return restore_record_by_id(session, Site, site_id)
