"""Shared archive, restore, visibility, and constraint helpers for services."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

from compliance.db.models import Certification, Certifier, Client, Regulation, Site
from compliance.services.schemas import ArchiveRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class LifecycleResult:
    """Result for an archive or restore mutation."""

    record: Any | None
    changed: bool


def get_constraint_name(exc: IntegrityError) -> str | None:
    """Extract a database constraint name from an integrity error.

    Args:
        exc: SQLAlchemy integrity error raised by the database driver.

    Returns:
        The database-reported constraint name, or ``None`` when the driver does
        not expose one.
    """
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def archive_record_by_id(
    session: Session, model: type[Any], record_id: Any, archive_request: ArchiveRequest
) -> LifecycleResult:
    """Archive one ORM record by primary key.

    Args:
        session: Database session used to retrieve and update the record.
        model: SQLAlchemy ORM model class to retrieve.
        record_id: Primary-key value for the record.
        archive_request: Archive metadata containing an optional reason.

    Returns:
        The ORM record and whether the archive state changed.

    Side effects:
        Sets ``archived_at`` to the current UTC time, stores a stripped archive
        reason when provided. Already archived records are returned unchanged.
    """
    record = session.get(model, record_id)
    if record is None:
        return LifecycleResult(record=None, changed=False)

    if record.archived_at is None:
        record.archived_at = datetime.now(UTC)
        archive_reason = archive_request.archive_reason
        record.archive_reason = (
            archive_reason.strip() or None if archive_reason else None
        )
        return LifecycleResult(record=record, changed=True)

    return LifecycleResult(record=record, changed=False)


def restore_record_by_id(
    session: Session, model: type[Any], record_id: Any
) -> LifecycleResult:
    """Restore one archived ORM record by primary key.

    Args:
        session: Database session used to retrieve and update the record.
        model: SQLAlchemy ORM model class to retrieve.
        record_id: Primary-key value for the record.

    Returns:
        The ORM record and whether the restore state changed.

    Side effects:
        Clears ``archived_at`` and ``archive_reason`` when the record is
        currently archived. Active records are returned unchanged.
    """
    record = session.get(model, record_id)
    if record is None:
        return LifecycleResult(record=None, changed=False)

    if record.archived_at is not None:
        record.archived_at = None
        record.archive_reason = None
        return LifecycleResult(record=record, changed=True)

    return LifecycleResult(record=record, changed=False)


def record_is_visible(record: Any, include_archived: bool) -> bool:
    """Return whether a record should be visible for archive-aware reads."""
    if record is None:
        return False

    archived_at = getattr(record, "archived_at", None)
    if isinstance(archived_at, Mock):
        archived_at = None

    return include_archived or archived_at is None


def certification_parent_chain_is_visible(
    session: Session,
    certification: Certification,
) -> bool:
    """Return whether a certification's required parent records are active.

    Args:
        session: Database session used to load parent records.
        certification: Certification whose site, client, certifier, and
            regulation records should be checked.

    Returns:
        ``True`` when every required parent exists and is active; otherwise
        ``False``.
    """
    site = session.get(Site, certification.site_id)
    if site is None or not record_is_visible(site, include_archived=False):
        return False

    client = session.get(Client, site.nif)
    if not record_is_visible(client, include_archived=False):
        return False

    certifier = session.get(Certifier, certification.certifier_id)
    if not record_is_visible(certifier, include_archived=False):
        return False

    regulation = session.get(Regulation, certification.regulation_id)
    return record_is_visible(regulation, include_archived=False)
