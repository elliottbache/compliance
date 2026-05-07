from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    CertifierCreate,
    CertifierOut,
)
from compliance.services.certifiers import (
    CertifierConflictError,
    CertifierOrganizationNameConflictError,
    get_certifier_by_id,
    get_certifiers,
    post_new_certifier,
)

router = APIRouter(prefix="/certifiers", tags=["certifiers"])


@router.get("")
def get_certifiers_route(
    session: SessionDep,
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


@router.get("/{certifier_id}")
def get_certifiers_by_id_route(
    certifier_id: Annotated[int, Path(ge=1)],
    session: SessionDep,
    include_archived: Annotated[bool, Query()] = False,
) -> CertifierOut:
    """Return one certifier by ID.

    Args:
        certifier_id: Primary key for the certifier.
        session: Database session provided by FastAPI dependency injection.
        include_archived: When true, return archived certifiers.

    Returns:
        Certifier record serialized with the public API response schema.

    Raises:
        HTTPException: If no visible certifier exists for the requested ID.
    """
    result = get_certifier_by_id(
        certifier_id, session, include_archived=include_archived
    )
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Certifier {certifier_id} not found."
        )

    return CertifierOut.model_validate(result)


@router.post("", status_code=201)
def post_new_certifier_route(
    certifier: CertifierCreate, session: SessionDep
) -> CertifierOut:
    """Create a new certifier record.

    Args:
        certifier: Certifier details supplied in the request body.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Created certifier details serialized with the public API response
        schema.

    Raises:
        HTTPException: If the certifier cannot be created, such as when it
            conflicts with an existing record.
    """
    try:
        new_certifier = post_new_certifier(certifier, session)

    except CertifierOrganizationNameConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=(
                "Certifier with organization name "
                f"{certifier.organization_name} already exists."
            ),
        ) from err

    except CertifierConflictError as err:
        raise HTTPException(
            status_code=409,
            detail="Certifier was not added because of a data conflict.",
        ) from err

    return CertifierOut.model_validate(new_certifier)
