"""Client service functions for listing, creation, archive, and restore."""

from compliance.db.models import (
    Client,
)
from compliance.services.lifecycle import (
    archive_record_by_id,
    get_constraint_name,
    restore_record_by_id,
)
from compliance.services.schemas import (
    ArchiveRequest,
    ClientCreate,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class ClientConflictError(Exception):
    """Raised when a client cannot be created because of existing data."""


class ClientNifConflictError(ClientConflictError):
    """Raised when a client NIF already exists."""


class ClientCompanyNameConflictError(ClientConflictError):
    """Raised when a client company name already exists."""


def get_clients(
    session: Session, *, limit: int | None, offset: int, include_archived: bool = False
) -> list[Client]:
    """Retrieve clients ordered by company name and NIF.

    Args:
        session: Database session used to execute the client query.
        limit: Maximum number of clients to return. If ``None``, all clients
            are returned.
        offset: Number of clients to skip before returning results.
        include_archived: When true, include archived clients in the results.

    Returns:
        Client ORM objects, or an empty list if no clients exist.
    """
    stmt = select(Client)
    if not include_archived:
        stmt = stmt.where(Client.archived_at.is_(None))

    stmt = stmt.order_by(Client.company_name, Client.nif).limit(limit).offset(offset)
    return list(session.execute(stmt).scalars().all())


def post_new_client(session: Session, client: ClientCreate) -> Client:
    """Persist a new client record.

    Args:
        session: Database session used to add and commit the client.
        client: Client data validated by the API layer.

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
            raise ClientNifConflictError(
                f"Client with NIF {client.nif} already exists."
            ) from exc

        if constraint_name == "uq_clients_company_name":
            raise ClientCompanyNameConflictError(
                f"Client with company name {client.company_name} already exists."
            ) from exc

        raise ClientConflictError(
            "Client was not added because of a data conflict."
        ) from exc

    return new_client


def post_client_archived_by_nif(
    session: Session, nif: str, *, archive_request: ArchiveRequest
) -> Client | None:
    """Archive a client by NIF.

    Args:
        session: Database session used to retrieve and update the client.
        nif: Unique fiscal identifier for the client to archive.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The client ORM object, or ``None`` if no matching client exists.

    Side effects:
        Sets ``archived_at`` to the current UTC time, stores a stripped archive
        reason when provided, and commits the session. Already archived clients
        are returned unchanged.
    """
    return archive_record_by_id(session, Client, nif, archive_request)


def post_client_restored_by_nif(session: Session, nif: str) -> Client | None:
    """Restore an archived client by NIF.

    Args:
        session: Database session used to retrieve and update the client.
        nif: Unique fiscal identifier for the client to restore.

    Returns:
        The client ORM object, or ``None`` if no matching client exists.

    Side effects:
        Clears ``archived_at`` and ``archive_reason`` and commits the session
        when the client is currently archived. Active clients are returned
        unchanged.
    """

    return restore_record_by_id(session, Client, nif)
