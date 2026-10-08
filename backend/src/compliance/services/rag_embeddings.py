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
from compliance.llm.rag.ollama_embeddings import OllamaEmbeddingProvider
from pydantic import BaseModel, ConfigDict
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, object_session, selectinload

_DEAFULT_TOTAL_CLOSEST_EMBEDDINGS = (
    8  # number of closest embeddings to the input findings to use from RAG retrieval
)
_DEAFULT_CLOSEST_EMBEDDINGS = (
    3  # number of closest embeddings to the input clause to use from RAG retrieval
)
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


@dataclass(frozen=True)
class ClosestEmbedding:
    """Embedding clause with its distance to the query."""

    embedding: RagClauseEmbedding
    distance: float


@dataclass(frozen=True)
class TopEmbedding:
    """Embedding clause with its distance to the finding."""

    closest_embedding: ClosestEmbedding
    finding_id: int


class RagClausePublicSchema(BaseModel):
    """Public schema containing necessary attributes for finding closest embeddings to query."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    citation_ref: str
    title: str | None
    path_text: str | None
    text: str


class TopClause(BaseModel):
    """One of closest RAG clauses to the site history with associated finding."""

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    rag_clause: RagClausePublicSchema
    finding_id: int


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


def embed_rag_queries(
    *, queries: dict[int, str], provider: EmbeddingProvider
) -> dict[int, list[float]]:
    """Generate embedding for RAG query."""
    _validate_model(provider.model)
    embeddings = {}
    for finding_id in queries:
        vector = provider.embed_text(queries[finding_id])
        _validate_vector(vector)
        embeddings[finding_id] = vector

    return embeddings


def find_top_embeddings(
    *,
    session: Session,
    query_embeddings: dict[int, list[float]],
    provider: EmbeddingProvider,
) -> list[TopEmbedding]:

    top_embeddings: list[TopEmbedding] = []
    for finding_id in query_embeddings:
        nearest_neighbors_to_vector = _find_closest_embeddings(
            session=session,
            query_embedding=query_embeddings[finding_id],
            provider=provider,
        )
        top_embeddings.extend(
            [
                TopEmbedding(finding_id=finding_id, closest_embedding=closest_embedding)
                for closest_embedding in nearest_neighbors_to_vector
            ]
        )
        top_embeddings.sort(
            key=lambda rag_embedding: rag_embedding.closest_embedding.distance
        )
        top_embeddings[8:] = []

    return top_embeddings


def _find_closest_embeddings(
    *, session: Session, query_embedding: list[float], provider: EmbeddingProvider
) -> list[ClosestEmbedding]:
    """Find the ``_DEAFULT_CLOSEST_EMBEDDINGS`` closest embeddings to the input vector representing
    a clause."""

    normalized_query_embedding = _validate_vector(query_embedding)
    distance_expression = RagClauseEmbedding.embedding.cosine_distance(
        normalized_query_embedding
    )
    model = _validate_model(provider.model)

    nearest_neighbors = session.execute(
        select(
            distance_expression,
            RagClauseEmbedding,
        )
        .where(
            RagClauseEmbedding.embedding_model == model,
            RagClauseEmbedding.dimensions == len(normalized_query_embedding),
        )
        .order_by(distance_expression)
        .limit(_DEAFULT_CLOSEST_EMBEDDINGS)
    ).all()

    return [
        ClosestEmbedding(embedding=embedding, distance=distance)
        for distance, embedding in nearest_neighbors
    ]


def sync_rag_clause_embeddings(
    session: Session, *, document: RagDocument, provider: EmbeddingProvider
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


if __name__ == "__main__":
    from datetime import date

    from compliance.db.db_access import get_engine
    from compliance.db.models import RagClause, RagDocument, Site
    from compliance.llm.rag.embedding_input import (
        build_site_analysis_query_embedding_input,
    )
    from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory

    sample_site = Site(
        id=101,
        nif="A12345678",
        city="Madrid",
        postal_code=28001,
        street="Mayor",
        street_number=10,
        suite=None,
        address_info=None,
        archived_at=None,
        archive_reason=None,
    )

    sample_site_history = SiteHistory(
        site_id=sample_site.id,
        inspection_count=1,
        latest_inspection_date=date(2026, 9, 15),
        certifications=[
            CertificationHistory(
                cert_id=201,
                result="Fail",
                resolution_date=None,
                reg_title="Workplace Safety Regulation",
                reg_description=(
                    "Establishes safety requirements for workplace facilities."
                ),
                certifier_org_name="Example Certification Services",
                inspection_date=date(2026, 9, 15),
                findings=[
                    FindingHistory(
                        finding_id=301,
                        finding=(
                            "The emergency exit was partially obstructed by "
                            "stored materials."
                        ),
                        rule_index="4.2",
                        rule_title="Emergency exits",
                        rule_description=(
                            "Emergency exits must remain clear and accessible."
                        ),
                    ),
                    FindingHistory(
                        finding_id=302,
                        finding=(
                            "The inspection record for one fire extinguisher "
                            "was not available."
                        ),
                        rule_index="5.1",
                        rule_title=None,
                        rule_description=(
                            "Fire-protection equipment must be inspected and "
                            "documented at the required intervals."
                        ),
                    ),
                ],
            )
        ],
    )

    queries = build_site_analysis_query_embedding_input(
        sample_site,
        sample_site_history,
    )

    for finding_id, query in queries.items():
        print(f"Finding ID: {finding_id}")
        print(query)
        print("-" * 80)

    embedding_provider = OllamaEmbeddingProvider()
    finding_embeddings = embed_rag_queries(queries=queries, provider=embedding_provider)
    print("finding_embeddings = ", finding_embeddings)

    # search RAG embeddings for closest 3 vectors for each and retrieve text from top 8 vectors
    with Session(get_engine()) as session:
        sample_embedding = session.scalar(
            select(RagClauseEmbedding)
            .where(RagClauseEmbedding.embedding.is_not(None))
            .order_by(RagClauseEmbedding.id)
            .limit(1)
        )

    top_embeddings = find_top_embeddings(
        session=session,
        query_embeddings=finding_embeddings,
        provider=embedding_provider,
    )
    print("top_embeddings = ", top_embeddings)

    # return RAG clauses
    closest_clauses = [
        TopClause(
            rag_clause=RagClausePublicSchema.model_validate(
                top_embedding.closest_embedding.embedding.rag_clause_embedding_clause_rel
            ),
            finding_id=top_embedding.finding_id,
        )
        for top_embedding in top_embeddings
    ]
    for closest_clause in closest_clauses:
        print(
            "closest_clause: ",
            closest_clause.rag_clause.title,
            ": ",
            closest_clause.rag_clause.text,
        )

    """with Session(get_engine()) as session:
        sample_embedding = session.scalar(
            select(RagClauseEmbedding)
            .where(RagClauseEmbedding.embedding.is_not(None))
            .order_by(RagClauseEmbedding.id)
            .limit(1)
        )

        if sample_embedding is None:
            raise SystemExit(
                "No RAG clause embeddings found. Import a RAG document first."
            )

        query_embedding = [float(value) for value in sample_embedding.embedding]
        closest_embeddings = _find_closest_embeddings(
            session=session,
            query_embedding=query_embedding,
        )

        print(f"Query embedding ID: {sample_embedding.id}")
        for result in closest_embeddings:
            print(
                f"embedding_id={result.embedding.id}, "
                f"clause_id={result.embedding.clause_id}, "
                f"distance={result.distance:.6f}"
            )

        top_embeddings = find_top_embeddings(session=session, query_embeddings={1: query_embedding})
        print(f"Query embedding ID: {sample_embedding.id}")
        for result in top_embeddings:
            print(
                f"finding_id={result.finding_id}, "
                f"embedding_id={result.closest_embedding.embedding.id}, "
                f"clause_id={result.closest_embedding.embedding.clause_id}, "
                f"distance={result.closest_embedding.distance:.6f}"
            )

        queries = {1: "here is the first query."}
        embeddings = embed_rag_queries(queries=queries)
        print("embeddings = ", embeddings)"""
