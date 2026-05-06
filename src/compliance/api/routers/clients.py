from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ClientCreate,
    ClientOut,
    SiteOut,
)
from compliance.services.clients import (
    ClientCompanyNameConflictError,
    ClientConflictError,
    ClientNifConflictError,
    get_client_by_nif,
    get_clients,
    post_new_client,
)
from compliance.services.sites import get_sites

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def get_clients_route(
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ClientOut]:
    """Return clients with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of clients to return.
        offset: Number of clients to skip before returning results.

    Returns:
        Client records serialized with the public API response schema.
    """
    clients = get_clients(session, limit, offset)
    return [ClientOut.model_validate(client) for client in clients]


@router.get("/{nif}")
def get_clients_by_nif_route(
    nif: Annotated[str, Path(min_length=9, max_length=9)], session: SessionDep
) -> ClientOut:
    """Return one client by NIF.

    Args:
        nif: Unique fiscal identifier for the client.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Client record serialized with the public API response schema.

    Raises:
        HTTPException: If no client exists for the requested NIF.
    """
    result = get_client_by_nif(nif, session)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Client {nif} not found.")

    return ClientOut.model_validate(result)


@router.get("/{nif}/sites")
def get_client_sites_route(
    nif: Annotated[str, Path(min_length=9, max_length=9)], session: SessionDep
) -> list[SiteOut]:
    """Return sites for one client by NIF.

    Args:
        nif: Unique fiscal identifier for the client whose sites should be
            retrieved.
        session: Database session provided by FastAPI dependency injection.

    Returns:
        Site records serialized with the public API response schema, or an
        empty list when the client exists without sites.

    Raises:
        HTTPException: If no client exists for the requested NIF.
    """
    client = get_client_by_nif(nif, session)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client {nif} not found.")

    sites = get_sites(session, nif=nif, limit=None, offset=0)
    if sites is None:
        return []

    return [SiteOut.model_validate(site) for site in sites]


@router.post("", status_code=201)
def post_new_client_route(client: ClientCreate, session: SessionDep) -> ClientOut:
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
    try:
        new_client = post_new_client(client, session)

    except ClientNifConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Client with NIF {client.nif} already exists.",
        ) from err

    except ClientCompanyNameConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=f"Client with company name {client.company_name} already exists.",
        ) from err

    except ClientConflictError as err:
        raise HTTPException(
            status_code=409, detail="Client was not added because of a data conflict."
        ) from err

    return ClientOut.model_validate(new_client)
