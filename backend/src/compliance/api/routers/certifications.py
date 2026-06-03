from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    CertificationAttachmentsOut,
    CertificationCreate,
    CertificationOut,
    FindingOut,
)
from compliance.services.certifications import (
    CertificationCertifierNotFoundError,
    CertificationConflictError,
    CertificationInspectorNotFoundError,
    CertificationRegulationNotFoundError,
    CertificationSiteNotFoundError,
    get_certification_attachments_by_id,
    get_certification_by_id,
    get_certifications,
    post_certification_archived_by_id,
    post_certification_restored_by_id,
    post_new_certification,
)
from compliance.services.findings import get_findings
from fastapi import APIRouter, HTTPException, Path, Query

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("")
def get_certifications_route(
    session: SessionDep,
    site_id: Annotated[int | None, Query(gt=0)] = None,
    open_only: Annotated[bool, Query()] = False,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[CertificationOut]:
    """Return certifications with optional filters and pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        site_id: Optional site ID used to return certifications for one site.
        open_only: When true, return certifications without a resolution date.
        limit: Maximum number of certifications to return.
        offset: Number of certifications to skip before returning results.
        include_archived: When true, include archived certifications and
            archived parent site, regulation, and certifier records.

    Returns:
        Certification records serialized with the public API response schema.

    Raises:
        HTTPException: If ``site_id`` is provided and no matching visible site
            exists.
    """
    certifications_list = get_certifications(
        session,
        site_id=site_id,
        open_only=open_only,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    if certifications_list is None:
        raise HTTPException(status_code=404, detail=f"Site does not exist: {site_id}")

    return certifications_list


@router.get("/{certification_id}")
def get_certification_by_id_route(
    session: SessionDep,
    certification_id: int,
    include_archived: Annotated[bool, Query()] = True,
) -> CertificationOut:
    """Return one certification by ID.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certification_id: Unique identifier for the certification to retrieve.
        include_archived: When true, return archived certifications and
            archived parent site, regulation, and certifier records.

    Returns:
        Certification details serialized with the public API response schema.

    Raises:
        HTTPException: If no visible certification exists for the requested ID.
    """
    certification = get_certification_by_id(
        session, certification_id, include_archived=include_archived
    )
    if certification is None:
        raise HTTPException(
            status_code=404,
            detail=f"No certification for this id found: {certification_id}",
        )

    return CertificationOut.model_validate(certification)


@router.get("/{certification_id}/attachments")
def get_certification_attachments_by_id_route(
    session: SessionDep,
    certification_id: int,
    include_archived: Annotated[bool, Query()] = False,
) -> CertificationAttachmentsOut:
    """Return attachment details for one certification by ID.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certification_id: Unique identifier for the certification whose
            attachments should be retrieved.
        include_archived: When true, include archived certification,
            attachment, site, certifier, regulation, finding, and rule records.
            By default, archived optional finding and rule links are omitted
            without hiding otherwise visible attachments.

    Returns:
        Certification attachments serialized with certification, regulation,
        and linked finding context, or an empty attachment list when the
        certification exists without attachments.

    Raises:
        HTTPException: If no visible certification exists for the requested ID.
    """
    certification_attachments = get_certification_attachments_by_id(
        session, certification_id, include_archived=include_archived
    )
    if certification_attachments is None:
        raise HTTPException(
            status_code=404,
            detail=f"No certification for this id found: {certification_id}",
        )

    return CertificationAttachmentsOut.model_validate(certification_attachments)


@router.get("/{certification_id}/findings")
def get_certification_findings_route(
    session: SessionDep,
    certification_id: int,
    include_archived: Annotated[bool, Query()] = False,
) -> list[FindingOut]:
    """Return findings for one certification by ID.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certification_id: Unique identifier for the certification whose
            findings should be retrieved.
        include_archived: When true, include archived certification, site,
            regulation, rule, finding, and linked attachment records.

    Returns:
        Finding records serialized with certification, regulation, rule, and
        linked attachment context, or an empty list when the certification
        exists without findings.

    Raises:
        HTTPException: If no visible certification exists for the requested ID.
    """
    certification = get_certification_by_id(
        session, certification_id, include_archived=include_archived
    )
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
        include_archived=include_archived,
    )


@router.post("", status_code=201)
def post_new_certification_route(
    session: SessionDep, certification: CertificationCreate
) -> CertificationOut:
    """Create a new certification record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certification: Certification details supplied in the request body.

    Returns:
        Created certification details serialized with the public API response schema.

    Raises:
        HTTPException: If the certification references missing parent data or
            another integrity conflict prevents creation.
    """
    try:
        new_certification = post_new_certification(session, certification)

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

    except CertificationInspectorNotFoundError as err:
        raise HTTPException(
            status_code=404,
            detail=f"Inspector {certification.inspector_id} does not exist.",
        ) from err

    except CertificationConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Certification was not added: {certification}.",
        ) from err

    return CertificationOut.model_validate(new_certification)


@router.post("/{certification_id}/archive", status_code=200)
def post_certification_archived_by_id_route(
    session: SessionDep,
    certification_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> CertificationOut:
    """Archive one certification by ID."""
    archive_request = archive_request or ArchiveRequest()

    certification = post_certification_archived_by_id(
        session, certification_id, archive_request=archive_request
    )
    if certification is None:
        raise HTTPException(
            status_code=404,
            detail=f"Certification does not exist: {certification_id}.",
        )

    return CertificationOut.model_validate(certification)


@router.post("/{certification_id}/restore", status_code=200)
def post_certification_restored_by_id_route(
    session: SessionDep, certification_id: Annotated[int, Path(ge=1)]
) -> CertificationOut:
    """Restore one archived certification by ID."""
    certification = post_certification_restored_by_id(session, certification_id)
    if certification is None:
        raise HTTPException(
            status_code=404,
            detail=f"Certification does not exist: {certification_id}.",
        )

    return CertificationOut.model_validate(certification)
