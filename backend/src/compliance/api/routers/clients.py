from typing import Annotated

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ArchiveRequest,
    ClientCreate,
    ClientOut,
)
from compliance.auth.authorization import require_role
from compliance.db.models import Role
from compliance.services.clients import (
    ClientCompanyNameConflictError,
    ClientConflictError,
    ClientNifConflictError,
    get_clients,
    post_client_archived_by_nif,
    post_client_restored_by_nif,
    post_new_client,
)
from compliance.services.schemas import UserOut
from fastapi import APIRouter, Depends, HTTPException, Path, Query

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
def get_clients_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.VIEWER))],
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: Annotated[bool, Query()] = False,
) -> list[ClientOut]:
    """Return clients with optional pagination.

    Args:
        session: Database session provided by FastAPI dependency injection.
        limit: Maximum number of clients to return.
        offset: Number of clients to skip before returning results.
        include_archived: When true, include archived clients.

    Returns:
        Client records serialized with the public API response schema.
    """
    clients = get_clients(
        session, limit=limit, offset=offset, include_archived=include_archived
    )
    return [ClientOut.model_validate(client) for client in clients]


@router.post("", status_code=201)
def post_new_client_route(
    session: SessionDep,
    _authorized_user: Annotated[UserOut, Depends(require_role(Role.ADMIN))],
    client: ClientCreate,
) -> ClientOut:
    """Create a new client record.

    Args:
        session: Database session provided by FastAPI dependency injection.
        client: Client details supplied in the request body.

    Returns:
        Created client details serialized with the public API response schema.

    Raises:
        HTTPException: If the client cannot be created, such as when it
            conflicts with an existing record.
    """
    try:
        new_client = post_new_client(session, client)

    except ClientNifConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=str(err),
        ) from err

    except ClientCompanyNameConflictError as err:
        raise HTTPException(
            status_code=409,
            detail=str(err),
        ) from err

    except ClientConflictError as err:
        raise HTTPException(status_code=409, detail=str(err)) from err

    return ClientOut.model_validate(new_client)


@router.post("/{nif}/archive", status_code=200)
def post_client_archived_by_nif_route(
    session: SessionDep,
    nif: Annotated[str, Path(min_length=9, max_length=9)],
    archive_request: ArchiveRequest | None = None,
) -> ClientOut:
    """Archive one client by NIF.

    Args:
        session: Database session provided by FastAPI dependency injection.
        nif: Unique fiscal identifier for the client to archive.
        archive_request: Optional archive metadata supplied in the request body.

    Returns:
        Archived client record serialized with the public API response schema.

    Raises:
        HTTPException: If no client exists for the requested NIF.
    """

    archive_request = archive_request or ArchiveRequest()

    client = post_client_archived_by_nif(session, nif, archive_request=archive_request)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client does not exist: {nif}.")

    return ClientOut.model_validate(client)


@router.post("/{nif}/restore", status_code=200)
def post_client_restored_by_nif_route(
    session: SessionDep, nif: Annotated[str, Path(min_length=9, max_length=9)]
) -> ClientOut:
    """Restore one archived client by NIF.

    Args:
        session: Database session provided by FastAPI dependency injection.
        nif: Unique fiscal identifier for the client to restore.

    Returns:
        Restored client record serialized with the public API response schema.

    Raises:
        HTTPException: If no client exists for the requested NIF.
    """

    client = post_client_restored_by_nif(session, nif)
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client does not exist: {nif}.")

    return ClientOut.model_validate(client)
