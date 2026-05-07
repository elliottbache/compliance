from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
    FindingOut,
)
from compliance.services.certifications import (
    CertificationCertifierNotFoundError,
    CertificationConflictError,
    CertificationRegulationNotFoundError,
    CertificationSiteNotFoundError,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications,
    post_new_certification,
)
from compliance.services.findings import get_findings

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("")
def get_certifications_route(
    session: SessionDep,
    site_id: Annotated[int | None, Query(gt=0)] = None,
    open_only: Annotated[bool, Query()] = False,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CertificationOut]:
    """Return certifications with optional filters and pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site ID used to return certifications for one site.
        open_only: When true, return certifications without a resolution date.
        limit: Maximum number of certifications to return.
        offset: Number of certifications to skip before returning results.

    Returns:
        Certification records serialized with the public API response schema.

    Raises:
        HTTPException: If ``site_id`` is provided and no matching site exists.
    """
    certifications_list = get_certifications(session, site_id, open_only, limit, offset)
    if certifications_list is None:
        raise HTTPException(status_code=404, detail=f"Site does not exist: {site_id}")

    return certifications_list


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


@router.get("/{certification_id}/findings")
def get_certification_findings_route(
    certification_id: int, session: SessionDep
) -> list[FindingOut]:
    """Return findings for one certification by ID.

    Args:
        certification_id: Unique identifier for the certification whose
            findings should be retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Finding records serialized with certification, regulation, rule, and
        linked attachment context, or an empty list when the certification
        exists without findings.

    Raises:
        HTTPException: If no certification exists for the requested ID.
    """
    certification = get_certification_by_id(certification_id, session)
    if certification is None:
        raise HTTPException(
            status_code=404,
            detail=f"No certification for this id found: {certification_id}",
        )

    return get_findings(
        session,
        site_id=None,
        certification_id=certification_id,
        rule_id=None,
        attachment_id=None,
        open_only=False,
    )


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
        HTTPException: If the certification references missing parent data or
            another integrity conflict prevents creation.
    """
    try:
        new_certification = post_new_certification(certification, session)

    except CertificationCertifierNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Certifier {certification.certifier_id} does not exist.",
        ) from err

    except CertificationRegulationNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Regulation {certification.regulation_id} does not exist.",
        ) from err

    except CertificationSiteNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Site {certification.site_id} does not exist.",
        ) from err

    except CertificationConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Certification was not added: {certification}.",
        ) from err

    return CertificationOut.model_validate(new_certification)
