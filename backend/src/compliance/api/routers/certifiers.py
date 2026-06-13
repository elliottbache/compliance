from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    CertifierCreate,
    CertifierOut,
)
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.certifiers import (
    CertifierConflictError,
    CertifierOrganizationNameConflictError,
    get_certifiers,
    post_certifier_archived_by_id,
    post_certifier_restored_by_id,
    post_new_certifier,
)
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException, Path, Query

router = APIRouter(prefix="/certifiers", tags=["certifiers"])


@router.get("")
def get_certifiers_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[CertifierOut]:
    """Return certifiers with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of certifiers to return.
        offset: Number of certifiers to skip before returning results.
        include_archived: When true, include archived certifiers.

    Returns:
        Certifier records serialized with the public API response schema.
    """
    certifiers = get_certifiers(
        session, limit=limit, offset=offset, include_archived=include_archived
    )
    return [CertifierOut.model_validate(certifier) for certifier in certifiers]


@router.post("", status_code=201)
def post_new_certifier_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    certifier: CertifierCreate,
) -> CertifierOut:
    """Create a new certifier record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certifier: Certifier details supplied in the request body.

    Returns:
        Created certifier details serialized with the public API response
        schema.

    Raises:
        HTTPException: If the certifier cannot be created, such as when it
            conflicts with an existing record.
    """
    try:
        new_certifier = post_new_certifier(session, certifier)

    except CertifierOrganizationNameConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=str(err),
        ) from err

    except CertifierConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err

    return CertifierOut.model_validate(new_certifier)


@router.post("/{certifier_id}/archive", status_code=200)
def post_certifier_archived_by_id_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    certifier_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> CertifierOut:
    """Archive one certifier by ID."""
    archive_request = archive_request or ArchiveRequest()

    certifier = post_certifier_archived_by_id(
        session, certifier_id, archive_request=archive_request
    )
    if certifier is None:
        raise HTTPException(
            status_code=404, detail=f"Certifier does not exist: {certifier_id}."
        )

    return CertifierOut.model_validate(certifier)


@router.post("/{certifier_id}/restore", status_code=200)
def post_certifier_restored_by_id_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    certifier_id: Annotated[int, Path(ge=1)],
) -> CertifierOut:
    """Restore one archived certifier by ID."""
    certifier = post_certifier_restored_by_id(session, certifier_id)
    if certifier is None:
        raise HTTPException(
            status_code=404, detail=f"Certifier does not exist: {certifier_id}."
        )

    return CertifierOut.model_validate(certifier)
