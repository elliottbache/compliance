from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    CertificationAttachmentsOut,
    CertificationOut,
)
from compliance.services.records import (
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications_by_site_id,
)

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("")
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


@router.get("/{certification_id}")
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


@router.get("/{certification_id}/attachments")
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
