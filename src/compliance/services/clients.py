from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    ClientInOut,
)
from compliance.db.models import (
    Client,
)


def get_clients(session: Session, limit: int | None, offset: int) -> list[ClientInOut]:
    """Retrieve clients ordered by company name and NIF.

    Args:
        session: Database session used to execute the client query.
        limit: Maximum number of clients to return. If ``None``, all clients
            are returned.
        offset: Number of clients to skip before returning results.

    Returns:
        Client records serialized with the public API schema, or an empty list
        if no clients exist.
    """
    stmt = (
        select(Client)
        .order_by(Client.company_name, Client.nif)
        .limit(limit)
        .offset(offset)
    )
    clients = session.execute(stmt).scalars().all()

    return [ClientInOut.model_validate(client) for client in clients]


def get_client_by_nif(nif: str, session: Session) -> ClientInOut | None:
    """Retrieve one client by NIF.

    Args:
        nif: Unique fiscal identifier for the client.
        session: Database session used to retrieve the client.

    Returns:
        Client record serialized with the public API schema, or ``None`` if no
        matching client exists.
    """
    client_db = session.get(Client, nif)

    return None if not client_db else ClientInOut.model_validate(client_db)


def post_new_client(client: ClientInOut, session: Session) -> Client | None:
    """Persist a new client record.

    Args:
        client: Client data validated by the API layer.
        session: Database session used to add and commit the client.

    Returns:
        The created Client ORM object, or ``None`` if an integrity conflict
        prevents the insert.

    """
    client_dict = client.model_dump()
    new_client = Client(**client_dict)
    try:
        session.add(new_client)
        session.commit()
    except IntegrityError:
        session.rollback()
        return None

    return new_client
