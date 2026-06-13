from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    RegulationCreate,
    RegulationOut,
)
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.regulations import (
    RegulationConflictError,
    RegulationTitleConflictError,
    get_regulations,
    post_new_regulation,
    post_regulation_archived_by_id,
    post_regulation_restored_by_id,
)
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException, Path, Query

router = APIRouter(prefix="/regulations", tags=["regulations"])


@router.get("")
def get_regulations_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    certifier_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[RegulationOut]:
    """Return regulations with optional filters and pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        certifier_id: Optional certifier ID used to return regulations
            certified by one certifier.
        limit: Maximum number of regulations to return.
        offset: Number of regulations to skip before returning results.
        include_archived: When true, include archived regulations and, when
            filtering by certifier, archived certifier/certification links.

    Returns:
        Regulation records serialized with the public API response schema.

    Raises:
        HTTPException: If ``certifier_id`` is provided and no matching visible
            certifier exists.
    """
    regulations_list = get_regulations(
        session,
        certifier_id=certifier_id,
        limit=limit,
        offset=offset,
        include_archived=include_archived,
    )
    if regulations_list is None:
        raise HTTPException(
            status_code=404, detail=f"Certifier does not exist: {certifier_id}"
        )

    return regulations_list


@router.post("", status_code=201)
def post_new_regulation_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    regulation: RegulationCreate,
) -> RegulationOut:
    """Create a new regulation record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        regulation: Regulation details supplied in the request body.

    Returns:
        Created regulation details serialized with the public API response
        schema.

    Raises:
        HTTPException: If the regulation conflicts with existing data.
    """
    try:
        new_regulation = post_new_regulation(session, regulation)

    except RegulationTitleConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=str(err),
        ) from err

    except RegulationConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err

    return RegulationOut.model_validate(new_regulation)


@router.post("/{regulation_id}/archive", status_code=200)
def post_regulation_archived_by_id_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    regulation_id: Annotated[int, Path(ge=1)],
    archive_request: ArchiveRequest | None = None,
) -> RegulationOut:
    """Archive one regulation by ID."""
    archive_request = archive_request or ArchiveRequest()

    regulation = post_regulation_archived_by_id(
        session, regulation_id, archive_request=archive_request
    )
    if regulation is None:
        raise HTTPException(
            status_code=404, detail=f"Regulation does not exist: {regulation_id}."
        )

    return RegulationOut.model_validate(regulation)


@router.post("/{regulation_id}/restore", status_code=200)
def post_regulation_restored_by_id_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    regulation_id: Annotated[int, Path(ge=1)],
) -> RegulationOut:
    """Restore one archived regulation by ID."""
    regulation = post_regulation_restored_by_id(session, regulation_id)
    if regulation is None:
        raise HTTPException(
            status_code=404, detail=f"Regulation does not exist: {regulation_id}."
        )

    return RegulationOut.model_validate(regulation)
