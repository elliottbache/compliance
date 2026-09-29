"""RAG document persistence helpers."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Literal

from compliance.db.models import RagClause, RagDocument
from compliance.llm.rag.extract_clauses import (
    RagClause as ExtractedRagClause,
)
from compliance.llm.rag.extract_clauses import (
    import_rag_clauses,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class RagDocumentConflictError(Exception):
    """Raised when a RAG document cannot be persisted because of existing data."""


@dataclass(frozen=True)
class RagDocumentImportResult:
    """Describe a freshness-gated RAG document and clause import."""

    document: RagDocument
    action: Literal["created", "updated", "skipped"]
    clauses_created: int = 0
    clauses_updated: int = 0
    clauses_deleted: int = 0
    clauses_unchanged: int = 0


@dataclass(frozen=True)
class _ClauseSyncResult:
    created: int
    updated: int
    deleted: int
    unchanged: int


def import_rag_document_from_parsed_json(
    session: Session,
    document: dict[str, Any],
) -> RagDocumentImportResult:
    """Atomically import a newer RAG document and its extracted clauses."""
    values = _rag_document_values(document)

    stmt = select(RagDocument).where(RagDocument.source_id == values["source_id"])
    rag_document = session.execute(stmt).scalar_one_or_none()
    action: Literal["created", "updated"]

    if rag_document is None:
        rag_document = RagDocument(**values)
        session.add(rag_document)
        action = "created"
    else:
        incoming_freshness = _freshness_datetime(
            updated_at=values["updated_at"],
            effective_date=values["effective_date"],
        )
        stored_freshness = _freshness_datetime(
            updated_at=rag_document.updated_at,
            effective_date=rag_document.effective_date,
        )

        if incoming_freshness <= stored_freshness:
            return RagDocumentImportResult(document=rag_document, action="skipped")

        action = "updated"

    try:
        extracted_clauses = import_rag_clauses(document)
        _validate_extracted_clauses(extracted_clauses)

        if action == "updated":
            for field, value in values.items():
                setattr(rag_document, field, value)

        session.flush()
        clause_result = _sync_rag_clauses(
            session,
            document_id=rag_document.id,
            extracted_clauses=extracted_clauses,
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise RagDocumentConflictError(
            "RAG document was not persisted because of a data conflict."
        ) from exc
    except Exception:
        session.rollback()
        raise

    return RagDocumentImportResult(
        document=rag_document,
        action=action,
        clauses_created=clause_result.created,
        clauses_updated=clause_result.updated,
        clauses_deleted=clause_result.deleted,
        clauses_unchanged=clause_result.unchanged,
    )


def _validate_extracted_clauses(clauses: list[ExtractedRagClause]) -> None:
    content_hashes = [
        _required_extracted_string(clause, "content_hash") for clause in clauses
    ]
    sort_keys = [_required_extracted_string(clause, "sort_key") for clause in clauses]

    if len(content_hashes) != len(set(content_hashes)):
        raise ValueError("Extracted RAG clauses contain duplicate content hashes.")

    if len(sort_keys) != len(set(sort_keys)):
        raise ValueError("Extracted RAG clauses contain duplicate sort keys.")


def _sync_rag_clauses(
    session: Session,
    *,
    document_id: int,
    extracted_clauses: list[ExtractedRagClause],
) -> _ClauseSyncResult:
    stmt = select(RagClause).where(RagClause.document_id == document_id)
    existing_clauses = list(session.scalars(stmt))
    original_values = {
        clause.id: _persisted_clause_values(clause) for clause in existing_clauses
    }
    existing_by_hash = {clause.content_hash: clause for clause in existing_clauses}
    existing_by_sort_key = {clause.sort_key: clause for clause in existing_clauses}
    matches: dict[int, RagClause] = {}
    used_clause_ids: set[int] = set()

    for index, extracted_clause in enumerate(extracted_clauses):
        content_hash = _required_extracted_string(extracted_clause, "content_hash")
        match = existing_by_hash.get(content_hash)
        if match is not None:
            matches[index] = match
            used_clause_ids.add(match.id)

    for index, extracted_clause in enumerate(extracted_clauses):
        if index in matches:
            continue

        sort_key = _required_extracted_string(extracted_clause, "sort_key")
        sort_match = existing_by_sort_key.get(sort_key)
        if sort_match is not None and sort_match.id not in used_clause_ids:
            matches[index] = sort_match
            used_clause_ids.add(sort_match.id)

    stale_clauses = [
        clause for clause in existing_clauses if clause.id not in used_clause_ids
    ]

    for clause in existing_clauses:
        clause.sort_key = f"__rag_sync__.{clause.id}"
    for clause in stale_clauses:
        session.delete(clause)
    session.flush()

    created = 0
    updated = 0
    unchanged = 0

    for index, extracted_clause in enumerate(extracted_clauses):
        values = _extracted_clause_values(extracted_clause)
        matched_clause = matches.get(index)

        if matched_clause is None:
            session.add(RagClause(document_id=document_id, **values))
            created += 1
            continue

        if original_values[matched_clause.id] == values:
            unchanged += 1
        else:
            updated += 1

        for field, value in values.items():
            setattr(matched_clause, field, value)

    return _ClauseSyncResult(
        created=created,
        updated=updated,
        deleted=len(stale_clauses),
        unchanged=unchanged,
    )


def _extracted_clause_values(clause: ExtractedRagClause) -> dict[str, Any]:
    return {
        "citation_ref": _required_extracted_string(clause, "citation_ref"),
        "title": clause["title"],
        "path_text": clause["path_text"],
        "text": _required_extracted_string(clause, "text"),
        "content_hash": _required_extracted_string(clause, "content_hash"),
        "sort_key": _required_extracted_string(clause, "sort_key"),
    }


def _required_extracted_string(clause: ExtractedRagClause, field: str) -> str:
    value = clause.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Extracted RAG clause requires {field}.")
    return value


def _persisted_clause_values(clause: RagClause) -> dict[str, Any]:
    return {
        "citation_ref": clause.citation_ref,
        "title": clause.title,
        "path_text": clause.path_text,
        "text": clause.text,
        "content_hash": clause.content_hash,
        "sort_key": clause.sort_key,
    }


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
        effective_date = updated_at.date() if updated_at is not None else _today_utc()

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


def _freshness_datetime(
    *,
    updated_at: datetime | None,
    effective_date: date | None,
) -> datetime:
    if updated_at is not None:
        if updated_at.tzinfo is None:
            return updated_at.replace(tzinfo=UTC)
        return updated_at.astimezone(UTC)

    fallback_date = effective_date or _today_utc()
    return datetime.combine(fallback_date, time.min, tzinfo=UTC)


def _today_utc() -> date:
    return datetime.now(UTC).date()


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
