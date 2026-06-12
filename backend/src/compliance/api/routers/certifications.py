from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    CertificationCreate,
    CertificationOut,
)
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.certifications import (
    CertificationCertifierNotFoundError,
    CertificationConflictError,
    CertificationInspectorInactiveError,
    CertificationInspectorNotFoundError,
    CertificationRegulationNotFoundError,
    CertificationSiteNotFoundError,
    get_certifications,
    post_certification_archived_by_id,
    post_certification_restored_by_id,
    post_new_certification,
)
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException, Path, Query

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get("")
def get_certifications_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    site_id: Annotated[int | None, Query(gt=0)] = None,
    open_only: Annotated[bool, Query()] = False,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
    inspector_id: Annotated[int | None, Query(gt=0)] = None,
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
        inspector_id: Optional inspector ID assigned to the certifications.

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
        inspector_id=inspector_id,
    )
    if certifications_list is None:
        raise HTTPException(status_code=404, detail=f"Site does not exist: {site_id}")

    return certifications_list


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

    except CertificationInspectorInactiveError as err:
        raise HTTPException(
            status_code=422,
            detail=f"Inspector {certification.inspector_id} is inactive.",
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
