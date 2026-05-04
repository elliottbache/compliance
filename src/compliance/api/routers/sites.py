from json import JSONDecodeError
from typing import Annotated

from anthropic import APIError
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from compliance._helpers import validate_llm_references
from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    SiteAttachmentsOut,
    SiteCertificationsOut,
    SiteOut,
)
from compliance.llm.schemas import SiteAnalysis
from compliance.schemas import SiteHistory
from compliance.services.records import (
    format_site_certifications,
    get_site_attachments,
    get_site_by_id,
    get_site_certifications,
    get_site_history,
)
from compliance.services.reports import (
    build_site_analysis_markdown,
)
from compliance.services.site_analysis import (
    summarize_previous_visits,
)

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("/{site_id}")
def get_site_by_id_route(site_id: int, session: SessionDep) -> SiteOut:
    """Return one site by ID.

    Args:
        site_id: Unique identifier for the site to retrieve.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site details serialized with the public API response schema.

    Raises:
        HTTPException: If no site exists for the requested ID.
    """
    site = get_site_by_id(site_id, session)
    if site is None:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}"
        )

    return SiteOut.model_validate(site)


@router.get("/{site_id}/attachments")
def get_site_attachments_route(site_id: int, session: SessionDep) -> SiteAttachmentsOut:
    """Return attachment details for one site.

    Args:
        site_id: Unique identifier for the site whose attachments should be
            retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site attachments serialized with certification, regulation, and finding
        context, or an empty attachment list when the site exists without
        attachments.

    Raises:
        HTTPException: If no site exists for the requested ID.
    """
    site = get_site_by_id(site_id, session)
    if site is None:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}"
        )

    site_attachments = get_site_attachments(site_id, session)
    if site_attachments is None:
        return SiteAttachmentsOut(site_id=site_id, attachments=[])

    return SiteAttachmentsOut.model_validate(site_attachments)


@router.get("/{site_id}/certifications")
def get_site_certifications_route(
    site_id: int,
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SiteCertificationsOut:
    """Return certifications for one site.

    Args:
        site_id: Unique identifier for the site whose certifications should be
            retrieved.
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of certifications to return. If omitted, all
            matching certifications are returned.
        offset: Number of matching certifications to skip before returning
            results.

    Returns:
        Site certifications serialized with the public API response schema, or
        an empty certification list when the site exists without certifications.

    Raises:
        HTTPException: If no site exists for the requested ID.
    """
    site = get_site_by_id(site_id, session)
    if site is None:
        raise HTTPException(
            status_code=404, detail=f"No site for this id found: {site_id}"
        )

    results = get_site_certifications(site_id, session, limit, offset)

    return format_site_certifications(site_id, results)


@router.get("/{site_id}/history")
def get_site_history_route(site_id: int, session: SessionDep) -> SiteHistory:
    """Return certification history for one site.

    Args:
        site_id: Unique identifier for the site whose history should be retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site history serialized with certification and finding details.

    Raises:
        HTTPException: If no certification history exists for the requested site.
    """
    site_history = get_site_history(site_id, session)
    if site_history is None:
        raise HTTPException(
            status_code=404,
            detail=f"No site history found for this id: {site_id}",
        )

    return SiteHistory.model_validate(site_history)


@router.post("/{site_id}/analysis-preview")
def create_site_analysis_preview_route(
    site_id: int, session: SessionDep
) -> SiteAnalysis:
    """Generate an AI analysis preview for one site's certification history.

    Args:
        site_id: Unique identifier for the site whose history should be
            analyzed.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Structured site analysis generated by the LLM and validated against
        the source site history.

    Raises:
        HTTPException: If no site history exists for the requested site, if the
            LLM call or response parsing fails, or if the generated analysis
            references evidence that is not present in the source site history.
    """
    return _create_site_analysis(site_id, session)


@router.post("/{site_id}/analysis-preview/markdown")
def create_site_analysis_markdown_preview_route(
    site_id: int, session: SessionDep
) -> Response:
    """Generate a Markdown AI analysis preview for one site's history.

    Args:
        site_id: Unique identifier for the site whose history should be
            analyzed.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        A text/markdown response containing the validated site analysis.

    Raises:
        HTTPException: If no site history exists for the requested site, if the
            LLM call or response parsing fails, or if the generated analysis
            references evidence that is not present in the source site history.
    """
    site_analysis = _create_site_analysis(site_id, session)

    return Response(
        content=build_site_analysis_markdown(site_analysis),
        media_type="text/markdown",
    )


def _create_site_analysis(site_id: int, session: Session) -> SiteAnalysis:
    """Create and validate a structured AI analysis for one site.

    Args:
        site_id: Unique identifier for the site whose history should be
            analyzed.
        session: Database session used to retrieve site history.

    Returns:
        Structured site analysis generated by the LLM.

    Raises:
        HTTPException: If no site history exists for the requested site, if the
            LLM call or response parsing fails, or if the generated analysis
            references evidence that is not present in the source site history.
    """
    site_history = get_site_history(site_id, session)
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
