from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    ClientCreate,
)
from compliance.db.models import (
    Client,
)
from compliance.services._helpers import get_constraint_name


class ClientConflictError(Exception):
    """Raised when a client cannot be created because of existing data."""


class ClientNifConflictError(ClientConflictError):
    """Raised when a client NIF already exists."""


class ClientCompanyNameConflictError(ClientConflictError):
    """Raised when a client company name already exists."""


def get_clients(session: Session, limit: int | None, offset: int) -> list[Client]:
    """Retrieve clients ordered by company name and NIF.

    Args:
        session: Database session used to execute the client query.
        limit: Maximum number of clients to return. If ``None``, all clients
            are returned.
        offset: Number of clients to skip before returning results.

    Returns:
        Client ORM objects, or an empty list if no clients exist.
    """
    stmt = (
        select(Client)
        .order_by(Client.company_name, Client.nif)
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(stmt).scalars().all())


def get_client_by_nif(nif: str, session: Session) -> Client | None:
    """Retrieve one client by NIF.

    Args:
        nif: Unique fiscal identifier for the client.
        session: Database session used to retrieve the client.

    Returns:
        Client ORM object, or ``None`` if no matching client exists.
    """
    return session.get(Client, nif)


def post_new_client(client: ClientCreate, session: Session) -> Client:
    """Persist a new client record.

    Args:
        client: Client data validated by the API layer.
        session: Database session used to add and commit the client.

    Returns:
        The created Client ORM object.

    Raises:
        ClientNifConflictError: If the client NIF already exists.
        ClientCompanyNameConflictError: If the company name already exists.
        ClientConflictError: If another integrity conflict prevents the insert.
    """
    client_dict = client.model_dump()
    new_client = Client(**client_dict)
    try:
        session.add(new_client)
        session.commit()

    except IntegrityError as exc:
        session.rollback()

        constraint_name = get_constraint_name(exc)

        if constraint_name == "pk_clients":
            raise ClientNifConflictError(client.nif) from exc

        if constraint_name == "uq_clients_company_name":
            raise ClientCompanyNameConflictError(client.company_name) from exc

        raise ClientConflictError() from exc

    return new_client
