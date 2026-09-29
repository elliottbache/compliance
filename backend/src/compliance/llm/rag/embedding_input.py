"""Build deterministic semantic input for RAG clause embeddings."""

import hashlib
import json

from compliance.db.models import RagClause, RagDocument
from compliance.llm.rag.extract_clauses import normalize_text

EMBEDDING_INPUT_VERSION = 1


def build_clause_embedding_input(
    document: RagDocument,
    clause: RagClause,
) -> str:
    """Build labeled embedding text from document and clause context."""
    document_title = _required_text(document.title, "document title")
    source_id = _required_text(document.source_id, "document source ID")
    jurisdiction = _required_text(document.jurisdiction, "document jurisdiction")
    citation_ref = _required_text(clause.citation_ref, "clause citation")
    clause_text = _required_text(clause.text, "clause text")
    path_text = normalize_text(clause.path_text)
    clause_title = normalize_text(clause.title)

    lines = [
        f"Document title: {document_title}",
        f"Source ID: {source_id}",
        f"Jurisdiction: {jurisdiction}",
    ]

    if path_text:
        lines.append(f"Path: {path_text}")

    lines.append(f"Citation: {citation_ref}")

    if clause_title:
        lines.append(f"Clause title: {clause_title}")

    lines.extend(["", "Text:", clause_text])

    return "\n".join(lines)


def build_clause_embedding_input_hash(
    document: RagDocument,
    clause: RagClause,
) -> str:
    """Hash the versioned embedding input used for stale detection."""
    payload = {
        "input": build_clause_embedding_input(document, clause),
        "version": EMBEDDING_INPUT_VERSION,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _required_text(value: object | None, field: str) -> str:
    normalized = normalize_text(value)
    if normalized is None:
        raise ValueError(f"Embedding input requires {field}.")
    return normalized
