from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ClientInOut,
)
from compliance.services.clients import (
    get_client_by_nif,
    get_clients,
    post_new_client,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def get_clients_route(
    session: SessionDep,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ClientInOut]:
    """Return clients with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of clients to return.
        offset: Number of clients to skip before returning results.

    Returns:
        Client records serialized with the public API response schema.
    """
    return get_clients(session, limit, offset)


@router.get("/{nif}")
def get_clients_by_nif_route(
    nif: Annotated[str, Path(min_length=9, max_length=9)], session: SessionDep
) -> ClientInOut:
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

    return ClientInOut.model_validate(result)


@router.post("", status_code=201)
def post_new_client_route(client: ClientInOut, session: SessionDep) -> ClientInOut:
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
    new_client = post_new_client(client, session)
    if new_client is None:
        raise HTTPException(status_code=409, detail=f"Client was not added: {client}.")

    return ClientInOut.model_validate(new_client)
