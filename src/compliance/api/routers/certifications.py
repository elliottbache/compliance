from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
)
from compliance.services.certifications import (
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications,
    post_new_certification,
)

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("")
def get_certifications_route(
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CertificationOut]:
    """Return certifications with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of certifications to return.
        offset: Number of certifications to skip before returning results.

    Returns:
        Certification records serialized with the public API response schema.
    """
    return get_certifications(session, limit, offset)


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
        and linked finding context, or an empty attachment list when the
        certification exists without attachments.

    Raises:
        HTTPException: If no certification exists for the requested ID.
    """
    certification_attachments = get_certification_attachments_by_id(
        certification_id, session
    )
    if certification_attachments is None:
        raise HTTPException(
            status_code=404,
            detail=f"No certification for this id found: {certification_id}",
        )

    return CertificationAttachmentsOut.model_validate(certification_attachments)


@router.post("", status_code=201)
def post_new_certification_route(
    certification: CertificationCreate, session: SessionDep
) -> CertificationOut:
    """Create a new certification record.

    Args:
        certification: Certification details supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created certification details serialized with the public API response schema.

    Raises:
        HTTPException: If the certification cannot be created, such as when it
            conflicts with an existing record or references missing parent data.
    """
    new_certification = post_new_certification(certification, session)
    if new_certification is None:
        raise HTTPException(
            status_code=409, detail=f"Certification was not added: {certification}."
        )

    return CertificationOut.model_validate(new_certification)
