from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    RegulationCreate,
    RegulationOut,
)
from compliance.services.regulations import (
    RegulationConflictError,
    RegulationTitleConflictError,
    get_regulation_by_id,
    get_regulations,
    post_new_regulation,
)

router = APIRouter(prefix="/regulations", tags=["regulations"])


@router.get("")
def get_regulations_route(
    session: SessionDep,
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
        include_archived: When true, include archived regulations.

    Returns:
        Regulation records serialized with the public API response schema.

    Raises:
        HTTPException: If ``certifier_id`` is provided and no matching
            certifier exists.
    """
    regulations_list = get_regulations(
        session, certifier_id, limit, offset, include_archived
    )
    if regulations_list is None:
        raise HTTPException(
            status_code=404, detail=f"Certifier does not exist: {certifier_id}"
        )

    return regulations_list


@router.get("/{regulation_id}")
def get_regulation_by_id_route(
    regulation_id: int,
    session: SessionDep,
    include_archived: Annotated[bool, Query()] = False,
) -> RegulationOut:
    """Return one regulation by ID.

    Args:
        regulation_id: Unique identifier for the regulation to retrieve.
        session: Database session provided by FastAPI dependency injection.
        include_archived: When true, return archived regulations.

    Returns:
        Regulation details serialized with the public API response schema.

    Raises:
        HTTPException: If no regulation exists for the requested ID.
    """
    regulation = get_regulation_by_id(regulation_id, session, include_archived)
    if regulation is None:
        raise HTTPException(
            status_code=404,
            detail=f"No regulation for this id found: {regulation_id}",
        )

    return RegulationOut.model_validate(regulation)


@router.post("", status_code=201)
def post_new_regulation_route(
    regulation: RegulationCreate, session: SessionDep
) -> RegulationOut:
    """Create a new regulation record.

    Args:
        regulation: Regulation details supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created regulation details serialized with the public API response
        schema.

    Raises:
        HTTPException: If the regulation conflicts with existing data.
    """
    try:
        new_regulation = post_new_regulation(regulation, session)

    except RegulationTitleConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Regulation with title {regulation.title} already exists.",
        ) from err

    except RegulationConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Regulation was not added: {regulation}.",
        ) from err

    return RegulationOut.model_validate(new_regulation)
