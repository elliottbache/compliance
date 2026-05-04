from fastapi import APIRouter, HTTPException

from compliance.api.deps import SessionDep
from compliance.api.schemas import (
    ClientInOut,
)
from compliance.services.records import (
    post_new_client,
)

router = APIRouter(prefix="/clients", tags=["clients"])


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
