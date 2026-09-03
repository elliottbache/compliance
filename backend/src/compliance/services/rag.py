"""RAG document persistence helpers."""

from datetime import UTC, date, datetime
from typing import Any

from compliance.db.models import RagDocument
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class RagDocumentConflictError(Exception):
    """Raised when a RAG document cannot be persisted because of existing data."""


def upsert_rag_document_from_parsed_json(
    session: Session,
    document: dict[str, Any],
) -> RagDocument:
    """Create or update a RAG document from parsed source JSON."""
    values = _rag_document_values(document)

    stmt = select(RagDocument).where(RagDocument.source_id == values["source_id"])
    rag_document = session.execute(stmt).scalar_one_or_none()

    if rag_document is None:
        rag_document = RagDocument(**values)
        session.add(rag_document)
    else:
        for field, value in values.items():
            setattr(rag_document, field, value)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise RagDocumentConflictError(
            "RAG document was not persisted because of a data conflict."
        ) from exc

    return rag_document


def _rag_document_values(document: dict[str, Any]) -> dict[str, Any]:
    source_id = _required_string(document, "id")
    title = _required_string(document, "title")
    source_kind = _required_string(document, "source_kind")
    jurisdiction = _required_string(document, "jurisdiction")
    status = _required_string(document, "status")
    updated_at = _parse_optional_datetime(document.get("updated_at"), "updated_at")
    effective_date = _parse_optional_date(
        document.get("effective_date"),
        "effective_date",
    )

    if effective_date is None:
        if updated_at is None:
            raise ValueError(
                "Parsed RAG document requires effective_date or updated_at."
            )
        effective_date = updated_at.date()

    return {
        "source_id": source_id,
        "title": title,
        "source_kind": source_kind,
        "jurisdiction": jurisdiction,
        "effective_date": effective_date,
        "updated_at": updated_at,
        "status": status,
        "source_url": document.get("source_url") or document.get("url_eli"),
    }


def _required_string(document: dict[str, Any], field: str) -> str:
    value = document.get(field)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Parsed RAG document requires {field}.")

    return value.strip()


def _parse_optional_date(value: object, field: str) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ValueError(f"Parsed RAG document has invalid {field}.") from exc

    raise ValueError(f"Parsed RAG document has invalid {field}.")


def _parse_optional_datetime(value: object, field: str) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"Parsed RAG document has invalid {field}.") from exc

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    raise ValueError(f"Parsed RAG document has invalid {field}.")
