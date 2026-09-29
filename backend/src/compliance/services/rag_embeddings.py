"""Persistence helpers for current RAG clause embeddings."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from compliance.db.models import RagClause, RagClauseEmbedding, RagDocument
from compliance.llm.rag.embedding_input import (
    build_clause_embedding_input,
    build_clause_embedding_input_hash,
)
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, object_session, selectinload

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RagClauseEmbeddingUpsertResult:
    """Describe the result of persisting one current clause embedding."""

    embedding: RagClauseEmbedding
    action: Literal["created", "updated", "unchanged"]


@dataclass(frozen=True)
class RagClauseEmbeddingSyncResult:
    """Summarize embedding synchronization for one RAG document."""

    created: int
    updated: int
    unchanged: int


class EmbeddingProvider(Protocol):
    """Describe the embedding provider required by the import workflow."""

    model: str

    def embed_text(self, text: str) -> list[float]:
        """Return one embedding vector for text."""
        ...


def is_rag_clause_embedding_stale(
    clause: RagClause,
    *,
    model: str,
    input_hash: str,
) -> bool:
    """Return whether a clause embedding is missing or no longer current."""
    normalized_model = _validate_model(model)
    normalized_hash = _validate_input_hash(input_hash)
    embedding = clause.rag_clause_embedding_rel

    if embedding is None:
        return True

    vector = embedding.embedding
    return (
        not vector
        or embedding.dimensions != len(vector)
        or embedding.embedding_model != normalized_model
        or embedding.input_hash != normalized_hash
    )


def sync_rag_clause_embeddings(
    session: Session,
    *,
    document: RagDocument,
    provider: EmbeddingProvider,
) -> RagClauseEmbeddingSyncResult:
    """Generate and persist only missing or stale embeddings for a document."""
    document_id = _persistent_document_id(session, document)
    model = _validate_model(provider.model)
    stmt = (
        select(RagClause)
        .where(RagClause.document_id == document_id)
        .options(selectinload(RagClause.rag_clause_embedding_rel))
        .order_by(RagClause.sort_key)
    )
    clauses = list(session.scalars(stmt))
    created = 0
    updated = 0
    unchanged = 0

    for clause in clauses:
        input_hash = build_clause_embedding_input_hash(document, clause)
        if not is_rag_clause_embedding_stale(
            clause,
            model=model,
            input_hash=input_hash,
        ):
            unchanged += 1
            continue

        embedding_input = build_clause_embedding_input(document, clause)
        vector = provider.embed_text(embedding_input)
        result = upsert_rag_clause_embedding(
            session,
            clause=clause,
            vector=vector,
            model=model,
            input_hash=input_hash,
        )

        if result.action == "created":
            created += 1
        elif result.action == "updated":
            updated += 1
        else:
            unchanged += 1

    return RagClauseEmbeddingSyncResult(
        created=created,
        updated=updated,
        unchanged=unchanged,
    )


def upsert_rag_clause_embedding(
    session: Session,
    *,
    clause: RagClause,
    vector: list[float],
    model: str,
    input_hash: str,
) -> RagClauseEmbeddingUpsertResult:
    """Create or update one clause embedding without committing the session."""
    clause_id = _persistent_clause_id(session, clause)
    normalized_model = _validate_model(model)
    normalized_hash = _validate_input_hash(input_hash)
    normalized_vector = _validate_vector(vector)

    stmt = select(RagClauseEmbedding).where(RagClauseEmbedding.clause_id == clause_id)
    with session.no_autoflush:
        embedding = session.scalar(stmt)
    dimensions = len(normalized_vector)

    if embedding is None:
        embedding = RagClauseEmbedding(
            clause_id=clause_id,
            embedding=normalized_vector,
            embedding_model=normalized_model,
            input_hash=normalized_hash,
            dimensions=dimensions,
            embedded_at=datetime.now(UTC),
        )
        session.add(embedding)
        action: Literal["created", "updated"] = "created"
    else:
        if (
            embedding.embedding == normalized_vector
            and embedding.embedding_model == normalized_model
            and embedding.input_hash == normalized_hash
            and embedding.dimensions == dimensions
        ):
            return RagClauseEmbeddingUpsertResult(
                embedding=embedding,
                action="unchanged",
            )

        embedding.embedding = normalized_vector
        embedding.embedding_model = normalized_model
        embedding.input_hash = normalized_hash
        embedding.dimensions = dimensions
        embedding.embedded_at = datetime.now(UTC)
        action = "updated"

    session.flush()
    return RagClauseEmbeddingUpsertResult(embedding=embedding, action=action)


def _persistent_clause_id(session: Session, clause: RagClause) -> int:
    state = inspect(clause)
    if (
        not state.persistent
        or object_session(clause) is not session
        or not state.identity
    ):
        raise ValueError("RAG clause must be persistent in the provided session.")
    return int(state.identity[0])


def _persistent_document_id(session: Session, document: RagDocument) -> int:
    state = inspect(document)
    if (
        not state.persistent
        or object_session(document) is not session
        or not state.identity
    ):
        raise ValueError("RAG document must be persistent in the provided session.")
    return int(state.identity[0])


def _validate_model(model: str) -> str:
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Embedding model cannot be empty.")
    return model.strip()


def _validate_input_hash(input_hash: str) -> str:
    if not isinstance(input_hash, str) or not _SHA256_PATTERN.fullmatch(input_hash):
        raise ValueError("Embedding input hash must be lowercase SHA-256 hexadecimal.")
    return input_hash


def _validate_vector(vector: list[float]) -> list[float]:
    if not isinstance(vector, list) or not vector:
        raise ValueError("Embedding vector cannot be empty.")

    normalized = []
    for value in vector:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Embedding vector must contain only finite numbers.")
        normalized.append(float(value))

    return normalized
