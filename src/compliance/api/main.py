"""FastAPI application entrypoint for compliance API routes."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    CertificationOut,
    ClientInOut,
    SiteAttachmentsOut,
    SiteOut,
)
from compliance.db.db_access import get_db
from compliance.schemas import SiteHistory
from compliance.services.query_db import (
    get_certification_by_id,
    get_site_attachments_by_id,
    get_site_by_id,
    get_site_history_by_id,
    post_new_client,
)

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
