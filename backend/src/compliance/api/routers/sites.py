from json import JSONDecodeError
from typing import Annotated

from anthropic import APIError
from compliance._helpers import validate_llm_references
from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    SiteAttachmentsOut,
    SiteCertificationsOut,
    SiteCreate,
    SiteOut,
)
from compliance.llm.schemas import SiteAnalysis
from compliance.schemas import SiteHistory
from compliance.services.site_analysis import (
    summarize_previous_visits,
)
from compliance.services.sites import (
    SiteClientNotFoundError,
    SiteConflictError,
    SiteNotFoundError,
    format_site_certifications,
    get_site_attachments,
    get_site_by_id,
    get_site_certifications,
    get_site_history,
    get_sites,
    post_new_site,
    post_site_archived_by_id,
    post_site_restored_by_id,
)
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("")
def get_sites_route(
    session: SessionDep,
    nif: Annotated[str | None, Query(min_length=9, max_length=9)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[SiteOut]:
    """Return sites with optional client filtering and pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        nif: Optional client NIF used to return sites for one client.
        limit: Maximum number of sites to return.
        offset: Number of sites to skip before returning results.
        include_archived: When true, include archived sites and archived parent
            clients.

    Returns:
        Site records serialized with the public API response schema.

    Raises:
        HTTPException: If ``nif`` is provided and no matching visible client
            exists.
    """
    sites = get_sites(
        session, nif=nif, limit=limit, offset=offset, include_archived=include_archived
    )
    if sites is None:
        raise HTTPException(status_code=404, detail=f"No client with this NIF: {nif}.")

    return [SiteOut.model_validate(site) for site in sites]


@router.get("/{site_id}")
def get_site_by_id_route(
    session: SessionDep,
    site_id: int,
    include_archived: Annotated[bool, Query()] = True,
) -> SiteOut:
    """Return one site by ID.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Unique identifier for the site to retrieve.
        include_archived: When true, return archived sites and archived parent
            clients.

    Returns:
        Site details serialized with the public API response schema.

    Raises:
        HTTPException: If no visible site exists for the requested ID.
    """
    try:
        site = get_site_by_id(session, site_id, include_archived=include_archived)
    except SiteNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}."
        ) from err
    except SiteClientNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"No client for this NIF found {site_id}."
        ) from err

    return SiteOut.model_validate(site)


@router.get("/{site_id}/attachments")
def get_site_attachments_route(
    session: SessionDep,
    site_id: Annotated[int, Path(ge=1)],
    include_archived: Annotated[bool, Query()] = False,
) -> SiteAttachmentsOut:
    """Return attachment details for one site.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Unique identifier for the site whose attachments should be
            retrieved.
        include_archived: When true, include archived site, certification,
            attachment, regulation, finding, and rule records. By default,
            archived optional finding and rule links are omitted without hiding
            otherwise visible attachments.

    Returns:
        Site attachments serialized with certification, regulation, and finding
        context, or an empty attachment list when the site exists without
        attachments.

    Raises:
        HTTPException: If no visible site exists for the requested ID or NIF.
    """
    try:
        site_attachments = get_site_attachments(
            session,
            site_id,
            include_archived=include_archived,
        )
    except SiteNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"No site for this id found: {site_id}.",
        ) from err
    except SiteClientNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"No client for this site found: {site_id}.",
        ) from err

    if site_attachments is None:
        return SiteAttachmentsOut(site_id=site_id, attachments=list())

    return SiteAttachmentsOut.model_validate(site_attachments)


@router.get("/{site_id}/certifications")
def get_site_certifications_route(
    session: SessionDep,
    site_id: int,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> SiteCertificationsOut:
    """Return certifications for one site.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Unique identifier for the site whose certifications should be
            retrieved.
        limit: Maximum number of certifications to return. If omitted, all
            matching certifications are returned.
        offset: Number of matching certifications to skip before returning
            results.
        include_archived: When true, include archived site, parent client, and
            certification records.

    Returns:
        Site certifications serialized with the public API response schema, or
        an empty certification list when the site exists without certifications.

    Raises:
        HTTPException: If no visible site exists for the requested ID, or if
            the site's parent client is not visible.
    """

    try:
        results = get_site_certifications(
            session,
            site_id,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )
    except SiteNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}."
        ) from err
    except SiteClientNotFoundError as err:
        raise HTTPException(
            status_code=404, detail=f"No client for this site found: {site_id}."
        ) from err

    return format_site_certifications(site_id, results)


@router.get("/{site_id}/history")
def get_site_history_route(
    session: SessionDep,
    site_id: int,
    include_archived: Annotated[bool, Query()] = False,
) -> SiteHistory:
    """Return certification history for one site.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Unique identifier for the site whose history should be retrieved.
        include_archived: When true, include archived site, certification,
            regulation, certifier, finding, and rule records. By default,
            archived optional finding and rule rows are omitted without hiding
            otherwise visible certifications.

    Returns:
        Site history serialized with certification and finding details.

    Raises:
        HTTPException: If no visible certification history exists for the
            requested site.
    """
    site_history = get_site_history(session, site_id, include_archived=include_archived)
    if site_history is None:
        raise HTTPException(
            status_code=404,
            detail=f"No site history found for this id: {site_id}",
        )

    return SiteHistory.model_validate(site_history)


@router.post("", status_code=201)
def post_new_site_route(session: SessionDep, site: SiteCreate) -> SiteOut:
    """Create a new site record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site: Site details supplied in the request body.

    Returns:
        Created site details serialized with the public API response schema.

    Raises:
        HTTPException: If the site cannot be created, such as when it conflicts
            with an existing record or references missing parent data.
    """
    try:
        new_site = post_new_site(session, site)

    except SiteClientNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Client {site.nif} does not exist.",
        ) from err

    except SiteConflictError as err:
        raise HTTPException(
            status_code=409, detail=f"Site was not added: {site}."
        ) from err

    return SiteOut.model_validate(new_site)


@router.post("/{site_id}/archive", status_code=200)
def post_site_archived_by_id_route(
    session: SessionDep,
    site_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> SiteOut:
    """Archive one site by ID."""
    archive_request = archive_request or ArchiveRequest()

    site = post_site_archived_by_id(session, site_id, archive_request=archive_request)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site does not exist: {site_id}.")

    return SiteOut.model_validate(site)


@router.post("/{site_id}/restore", status_code=200)
def post_site_restored_by_id_route(
    session: SessionDep, site_id: Annotated[int, Path(ge=1)]
) -> SiteOut:
    """Restore one archived site by ID."""
    site = post_site_restored_by_id(session, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site does not exist: {site_id}.")

    return SiteOut.model_validate(site)


@router.post("/{site_id}/analysis")
def create_site_analysis_route(session: SessionDep, site_id: int) -> SiteAnalysis:
    """Generate an AI analysis for one site's certification history.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Unique identifier for the site whose history should be
            analyzed.

    Returns:
        Structured site analysis generated by the LLM and validated against
        the source site history.

    Raises:
        HTTPException: If no site history exists for the requested site, if the
            LLM call or response parsing fails, or if the generated analysis
            references evidence that is not present in the source site history.
    """
    return _create_site_analysis(session, site_id)


def _create_site_analysis(session: Session, site_id: int) -> SiteAnalysis:
    """Create and validate a structured AI analysis for one site.

    Args:
        session: Database session used to retrieve site history.
        site_id: Unique identifier for the site whose history should be
            analyzed.

    Returns:
        Structured site analysis generated by the LLM.

    Raises:
        HTTPException: If no site history exists for the requested site, if the
            LLM call or response parsing fails, or if the generated analysis
            references evidence that is not present in the source site history.
    """
    site_history = get_site_history(session, site_id)
    if site_history is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found.")

    try:
        site_analysis = summarize_previous_visits(site_history)
    except (APIError, ValidationError, JSONDecodeError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed for site {site_id}.",
        ) from exc

    if not validate_llm_references(site_analysis, site_history):
        raise HTTPException(
            status_code=502,
            detail=f"LLM model returned invalid evidence for site {site_id}.",
        )

    return site_analysis
