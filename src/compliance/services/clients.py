from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from compliance.api.schemas import (
    ArchiveRequest,
    ClientCreate,
)
from compliance.db.models import (
    Client,
)
from compliance.services._helpers import get_constraint_name, record_is_visible


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


def get_client_by_nif(
    nif: str, session: Session, *, include_archived: bool = False
) -> Client | None:
    """Retrieve one client by NIF.

    Args:
        nif: Unique fiscal identifier for the client.
        session: Database session used to retrieve the client.
        include_archived: When true, return archived clients.

    Returns:
        Client ORM object, or ``None`` if no matching visible client exists.
    """
    client = session.get(Client, nif)
    return client if record_is_visible(client, include_archived) else None


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

        if constraint_name == "clients_pkey":
            raise ClientNifConflictError(client.nif) from exc

        if constraint_name == "uq_company_name":
            raise ClientCompanyNameConflictError(client.company_name) from exc

        raise ClientConflictError() from exc

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

    client = session.get(Client, nif)
    if client is None:
        return None

    if client.archived_at is None:
        client.archived_at = datetime.now(UTC)
        archive_reason = archive_request.archive_reason
        client.archive_reason = (
            archive_reason.strip() or None if archive_reason else None
        )
        session.commit()

    return client


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

    client = session.get(Client, nif)
    if client is None:
        return None

    if client.archived_at is not None:
        client.archived_at = None
        client.archive_reason = None
        session.commit()

    return client
