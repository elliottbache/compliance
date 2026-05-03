"""FastAPI application entrypoint for compliance API routes."""

from json import JSONDecodeError
from typing import Annotated

from anthropic import APIError
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from compliance._helpers import validate_llm_references
from compliance.api.schemas import (
    AttachmentCreate,
    AttachmentOut,
    AttachmentWithContextOut,
    CertificationAttachmentsOut,
    CertificationOut,
    ClientInOut,
    FindingOut,
    SiteAttachmentsOut,
    SiteOut,
)
from compliance.db.db_access import get_db
from compliance.llm.anthropic_api import (
    render_site_analysis_markdown,
    summarize_previous_visits,
)
from compliance.llm.schemas import SiteAnalysis
from compliance.logging_utils import configure_logging
from compliance.schemas import SiteHistory
from compliance.services.query_db import (
    AttachmentCertificationNotFoundError,
    AttachmentConflictError,
    AttachmentFindingCertificationMismatchError,
    AttachmentFindingNotFoundError,
    get_attachment_by_id,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications_by_site_id,
    get_findings,
    get_site_attachments_by_id,
    get_site_by_id,
    get_site_history_by_id,
    post_new_attachment,
    post_new_client,
)

configure_logging(level="DEBUG")
app = FastAPI()


SessionDep = Annotated[Session, Depends(get_db)]


@app.get("/sites/{site_id}")
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


@app.get("/certifications/{certification_id}")
def get_certification_by_id_route(
    certification_id: int, session: SessionDep
) -> CertificationOut:
    """Return one certification by ID.

    Args:
        certification_id: Unique identifier for the certification to retrieve.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Certification details serialized with the public API response schema.

    Raises:
        HTTPException: If no certification exists for the requested ID.
    """
    certification = get_certification_by_id(certification_id, session)
    if certification is None:
        raise HTTPException(
            status_code=404,
            detail=f"No certification for this id found: {certification_id}",
        )

    return CertificationOut.model_validate(certification)


@app.get("/certifications/{certification_id}/attachments")
def get_certification_attachments_by_id_route(
    certification_id: int, session: SessionDep
) -> CertificationAttachmentsOut:
    """Return attachment details for one certification by ID.

    Args:
        certification_id: Unique identifier for the certification whose
            attachments should be retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Certification attachments serialized with certification, regulation,
        and linked finding context.

    Raises:
        HTTPException: If no certification exists for the requested ID.
    """
    certification_attachments = get_certification_attachments_by_id(
        certification_id, session
    )
    if certification_attachments is None:
        raise HTTPException(
            status_code=404,
            detail=f"No attachments found for certification {certification_id}",
        )

    return CertificationAttachmentsOut.model_validate(certification_attachments)


@app.get("/sites/{site_id}/history")
def get_site_history_by_id_route(site_id: int, session: SessionDep) -> SiteHistory:
    """Return certification history for one site by ID.

    Args:
        site_id: Unique identifier for the site whose history should be retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site history serialized with certification and finding details.

    Raises:
        HTTPException: If no certification history exists for the requested site.
    """
    site_history = get_site_history_by_id(site_id, session)
    if site_history is None:
        raise HTTPException(
            status_code=404,
            detail=f"No site history found for this id: {site_id}",
        )

    return SiteHistory.model_validate(site_history)


@app.get("/sites/{site_id}/attachments")
def get_site_attachments_by_id_route(
    site_id: int, session: SessionDep
) -> SiteAttachmentsOut:
    """Return attachment details for one site by ID.

    Args:
        site_id: Unique identifier for the site whose attachments should be
            retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site attachments serialized with certification, regulation, and finding
        context.

    Raises:
        HTTPException: If no attachments exist for the requested site.
    """
    site_attachments = get_site_attachments_by_id(site_id, session)
    if site_attachments is None:
        raise HTTPException(
            status_code=404, detail=f"No attachments found for site {site_id}"
        )

    return SiteAttachmentsOut.model_validate(site_attachments)


@app.post("/clients", status_code=201)
def post_new_client_route(client: ClientInOut, session: SessionDep) -> ClientInOut:
    """Create a new client record.

    Args:
        client: Client details supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created client details serialized with the public API response schema.

    Raises:
        HTTPException: If the client cannot be created, such as when it
            conflicts with an existing record.
    """
    new_client = post_new_client(client, session)
    if new_client is None:
        raise HTTPException(status_code=409, detail=f"Client was not added: {client}.")

    return ClientInOut.model_validate(new_client)


@app.get("/certifications")
def get_certifications_by_site_id_route(
    site_id: int,
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CertificationOut]:
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
        Certifications serialized with the public API response schema or [] if no
        certifications were found for this site_id.
    """
    results = get_certifications_by_site_id(site_id, session, limit, offset)

    return [CertificationOut.model_validate(row) for row in results]


@app.get("/findings")
def get_findings_route(
    session: SessionDep,
    site_id: int | None = None,
    rule_id: int | None = None,
    open_only: bool = False,
) -> list[FindingOut]:
    """Return findings with optional filters.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site identifier used to limit findings to one site.
        rule_id: Optional rule identifier used to limit findings to one rule.
        open_only: When true, only return findings whose certification has no
            resolution date.

    Returns:
        Finding records serialized with certification, regulation, and rule
        context.
    """
    return get_findings(session, site_id, rule_id, open_only)


@app.get("/attachments/{attachment_id}")
def get_attachment_by_id_route(
    attachment_id: int, session: SessionDep
) -> AttachmentWithContextOut:
    """Return one attachment with certification, regulation, and finding context.

    Args:
        attachment_id: Unique identifier for the attachment to retrieve.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Attachment details serialized with certification, regulation, and
        linked finding context.

    Raises:
        HTTPException: If no attachment exists for the requested ID.
    """
    result = get_attachment_by_id(attachment_id, session)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Attachment {attachment_id} not found."
        )

    return AttachmentWithContextOut.model_validate(result)


@app.post("/attachments", status_code=201)
def post_new_attachment_route(
    attachment: AttachmentCreate, session: SessionDep
) -> AttachmentOut:
    """Create a new attachment metadata record.

    Args:
        attachment: Attachment metadata supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created attachment metadata with generated storage and certification
        context fields.

    Raises:
        HTTPException: If the parent certification or linked findings are
            missing, if a finding belongs to another certification, or if the
            attachment conflicts with existing stored data.
    """
    try:
        new_attachment = post_new_attachment(attachment, session)
    except AttachmentCertificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AttachmentFindingCertificationMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AttachmentConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AttachmentOut.model_validate(new_attachment)


@app.post("/sites/{site_id}/analysis-preview")
def analyze_site(site_id: int, session: SessionDep) -> SiteAnalysis:
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


@app.post("/sites/{site_id}/analysis-preview/markdown")
def analyze_site_return_markdown(site_id: int, session: SessionDep) -> Response:
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
        content=render_site_analysis_markdown(site_analysis),
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
    site_history = get_site_history_by_id(site_id, session)
    if site_history is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found.")

    try:
        _, _, site_analysis = summarize_previous_visits(site_history)
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
