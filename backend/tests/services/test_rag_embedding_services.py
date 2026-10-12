from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from compliance.db.models import RagClause, RagClauseEmbedding, RagDocument
from compliance.services.rag_embeddings import (
    ClosestEmbedding,
    _find_closest_embeddings,
    embed_rag_queries,
    find_top_embeddings,
    is_rag_clause_embedding_stale,
    upsert_rag_clause_embedding,
)
from pgvector_test_database import temporary_pgvector_database
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

INPUT_HASH = "a" * 64


class TestEmbedRagQueries:
    def test_embeds_each_finding_and_preserves_association(self) -> None:
        provider = SimpleNamespace(
            model="embed-model",
            embed_text=MagicMock(side_effect=[[0.1, 0.2], [0.3, 0.4]]),
        )

        result = embed_rag_queries(
            queries={10: "first query", 20: "second query"}, provider=provider
        )

        assert result == {10: [0.1, 0.2], 20: [0.3, 0.4]}
        assert provider.embed_text.call_args_list == [
            call("first query"),
            call("second query"),
        ]

    @pytest.mark.parametrize("model", ["", "   "])
    def test_rejects_empty_model_before_embedding(self, model) -> None:
        provider = SimpleNamespace(model=model, embed_text=MagicMock())

        with pytest.raises(ValueError, match="model cannot be empty"):
            embed_rag_queries(queries={10: "query"}, provider=provider)

        provider.embed_text.assert_not_called()

    @pytest.mark.parametrize("vector", [[], [float("nan")], [True]])
    def test_rejects_invalid_provider_vector(self, vector) -> None:
        provider = SimpleNamespace(
            model="embed-model", embed_text=MagicMock(return_value=vector)
        )

        with pytest.raises(ValueError, match="Embedding vector"):
            embed_rag_queries(queries={10: "query"}, provider=provider)


class TestFindClosestEmbeddings:
    def test_filters_by_model_dimensions_and_active_document(self) -> None:
        session = MagicMock()
        session.execute.return_value.all.return_value = []

        result = _find_closest_embeddings(
            session=session,
            query_embedding=[0.1, 0.2, 0.3],
            provider=SimpleNamespace(model="embed-model"),
        )

        assert result == []
        statement = session.execute.call_args.args[0]
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)

        assert "JOIN rag_clauses" in sql
        assert "JOIN rag_documents" in sql
        assert "rag_clause_embeddings.embedding_model" in sql
        assert "rag_clause_embeddings.dimensions" in sql
        assert "rag_documents.status" in sql
        assert "embed-model" in compiled.params.values()
        assert 3 in compiled.params.values()
        assert "active" in compiled.params.values()

    @pytest.mark.pgvector_integration
    def test_executes_cosine_ranking_and_filters_with_pgvector(self) -> None:
        with temporary_pgvector_database() as engine:
            with engine.begin() as connection:
                connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                RagDocument.metadata.create_all(
                    connection,
                    tables=[
                        RagDocument.__table__,
                        RagClause.__table__,
                        RagClauseEmbedding.__table__,
                    ],
                )

            with Session(engine) as session:
                rows = [
                    ("relevant", "active", "embed-model", [1.0, 0.0, 0.0]),
                    ("nearby", "active", "embed-model", [0.9, 0.1, 0.0]),
                    ("distractor", "active", "embed-model", [0.0, 1.0, 0.0]),
                    ("fourth", "active", "embed-model", [-1.0, 0.0, 0.0]),
                    ("inactive", "inactive", "embed-model", [1.0, 0.0, 0.0]),
                    ("wrong-model", "active", "other-model", [1.0, 0.0, 0.0]),
                    ("wrong-dimensions", "active", "embed-model", [1.0, 0.0]),
                ]
                for index, (citation, status, model, vector) in enumerate(
                    rows, start=1
                ):
                    document = RagDocument(
                        source_id=f"EVAL-{index}",
                        title=f"Document {index}",
                        source_kind="evaluation",
                        jurisdiction="Spain",
                        effective_date=datetime(2026, 1, 1).date(),
                        updated_at=None,
                        status=status,
                        source_url=None,
                    )
                    clause = RagClause(
                        citation_ref=citation,
                        title=citation,
                        path_text=None,
                        text=f"Clause {index}",
                        content_hash=f"{index:064x}",
                        sort_key=f"{index:06d}",
                    )
                    document.rag_document_clause_rel.append(clause)
                    session.add(document)
                    session.flush()
                    session.add(
                        RagClauseEmbedding(
                            clause_id=clause.id,
                            embedding=vector,
                            embedding_model=model,
                            input_hash="a" * 64,
                            dimensions=len(vector),
                            embedded_at=datetime.now(UTC),
                        )
                    )
                session.commit()

                results = _find_closest_embeddings(
                    session=session,
                    query_embedding=[1.0, 0.0, 0.0],
                    provider=SimpleNamespace(model="embed-model"),
                )

                assert [
                    result.embedding.rag_clause_embedding_clause_rel.citation_ref
                    for result in results
                ] == ["relevant", "nearby", "distractor"]


class TestFindTopEmbeddings:
    def test_associates_results_with_each_finding(self, monkeypatch) -> None:
        first = ClosestEmbedding(embedding=SimpleNamespace(), distance=0.1)
        second = ClosestEmbedding(embedding=SimpleNamespace(), distance=0.2)
        monkeypatch.setattr(
            "compliance.services.rag_embeddings._find_closest_embeddings",
            MagicMock(side_effect=[[first], [second]]),
        )

        results = find_top_embeddings(
            session=MagicMock(),
            query_embeddings={10: [1.0], 20: [2.0]},
            provider=SimpleNamespace(model="embed-model"),
        )

        assert [
            (result.finding_id, result.closest_embedding.distance) for result in results
        ] == [
            (10, 0.1),
            (20, 0.2),
        ]

    def test_keeps_only_eight_closest_results(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "compliance.services.rag_embeddings._find_closest_embeddings",
            MagicMock(
                side_effect=[
                    [
                        ClosestEmbedding(
                            embedding=SimpleNamespace(), distance=float(distance)
                        )
                        for distance in distances
                    ]
                    for distances in ([1, 4, 7], [2, 5, 8], [3, 6, 9])
                ]
            ),
        )

        results = find_top_embeddings(
            session=MagicMock(),
            query_embeddings={10: [1.0], 20: [2.0], 30: [3.0]},
            provider=SimpleNamespace(model="embed-model"),
        )

        assert [result.closest_embedding.distance for result in results] == [
            1.0,
            2.0,
            3.0,
            4.0,
            5.0,
            6.0,
            7.0,
            8.0,
        ]


def _persisted_clause(sqlite_session) -> RagClause:
    document = RagDocument(
        source_id="BOE-A-2018-16673",
        title="Organic Law 3/2018",
        source_kind="public_regulation",
        jurisdiction="Spain",
        effective_date=datetime(2018, 12, 5).date(),
        updated_at=None,
        status="active",
        source_url=None,
    )
    clause = RagClause(
        citation_ref="Artículo 1",
        title="Purpose",
        path_text="Título I",
        text="Clause text.",
        content_hash="b" * 64,
        sort_key="000001",
    )
    document.rag_document_clause_rel.append(clause)
    sqlite_session.add(document)
    sqlite_session.commit()
    return clause


class TestUpsertRagClauseEmbedding:
    def test_creates_embedding_without_committing(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        clause = _persisted_clause(sqlite_session)
        commit = MagicMock()
        monkeypatch.setattr(sqlite_session, "commit", commit)

        result = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1, 2.5, -3],
            model=" embed-model ",
            input_hash=INPUT_HASH,
        )

        assert result.action == "created"
        assert result.embedding.id is not None
        assert result.embedding.clause_id == clause.id
        assert result.embedding.embedding == [1.0, 2.5, -3.0]
        assert result.embedding.embedding_model == "embed-model"
        assert result.embedding.input_hash == INPUT_HASH
        assert result.embedding.dimensions == 3
        assert result.embedding.embedded_at.tzinfo is not None
        commit.assert_not_called()

    def test_updates_existing_embedding_and_preserves_id(self, sqlite_session) -> None:
        clause = _persisted_clause(sqlite_session)
        original = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="first-model",
            input_hash=INPUT_HASH,
        )
        sqlite_session.commit()

        result = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[3.0, 4.0, 5.0],
            model="second-model",
            input_hash="c" * 64,
        )

        assert result.action == "updated"
        assert result.embedding.id == original.embedding.id
        assert result.embedding.embedding == [3.0, 4.0, 5.0]
        assert result.embedding.embedding_model == "second-model"
        assert result.embedding.input_hash == "c" * 64
        assert result.embedding.dimensions == 3
        assert sqlite_session.query(RagClauseEmbedding).count() == 1

    def test_returns_unchanged_without_flushing(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        clause = _persisted_clause(sqlite_session)
        original = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="embed-model",
            input_hash=INPUT_HASH,
        )
        sqlite_session.commit()
        embedded_at = original.embedding.embedded_at
        flush = MagicMock(wraps=sqlite_session.flush)
        monkeypatch.setattr(sqlite_session, "flush", flush)

        result = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="embed-model",
            input_hash=INPUT_HASH,
        )

        assert result.action == "unchanged"
        assert result.embedding.embedded_at == embedded_at
        flush.assert_not_called()

    def test_embedding_round_trips_and_is_deleted_with_clause(
        self,
        sqlite_session,
    ) -> None:
        clause = _persisted_clause(sqlite_session)
        result = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[0.1, 0.2, 0.3],
            model="embed-model",
            input_hash=INPUT_HASH,
        )
        embedding_id = result.embedding.id
        sqlite_session.commit()
        sqlite_session.expire_all()

        persisted = sqlite_session.get(RagClauseEmbedding, embedding_id)
        assert persisted is not None
        assert persisted.embedding == [0.1, 0.2, 0.3]

        sqlite_session.delete(sqlite_session.get(RagClause, clause.id))
        sqlite_session.commit()

        assert sqlite_session.get(RagClauseEmbedding, embedding_id) is None

    def test_rejects_clause_outside_provided_session(self, sqlite_session) -> None:
        clause = RagClause(
            citation_ref="Artículo 1",
            text="Clause text.",
            content_hash="b" * 64,
            sort_key="000001",
        )

        with pytest.raises(ValueError, match="persistent in the provided session"):
            upsert_rag_clause_embedding(
                sqlite_session,
                clause=clause,
                vector=[1.0],
                model="embed-model",
                input_hash=INPUT_HASH,
            )

    @pytest.mark.parametrize("model", ["", "  "])
    def test_rejects_empty_model(self, sqlite_session, model) -> None:
        clause = _persisted_clause(sqlite_session)

        with pytest.raises(ValueError, match="model cannot be empty"):
            upsert_rag_clause_embedding(
                sqlite_session,
                clause=clause,
                vector=[1.0],
                model=model,
                input_hash=INPUT_HASH,
            )

    @pytest.mark.parametrize(
        "input_hash",
        ["short", "A" * 64, "g" * 64],
    )
    def test_rejects_invalid_input_hash(self, sqlite_session, input_hash) -> None:
        clause = _persisted_clause(sqlite_session)

        with pytest.raises(ValueError, match="lowercase SHA-256"):
            upsert_rag_clause_embedding(
                sqlite_session,
                clause=clause,
                vector=[1.0],
                model="embed-model",
                input_hash=input_hash,
            )

    @pytest.mark.parametrize(
        "vector",
        [
            [],
            [True],
            ["not-a-number"],
            [float("nan")],
            [float("inf")],
        ],
    )
    def test_rejects_invalid_vector(self, sqlite_session, vector) -> None:
        clause = _persisted_clause(sqlite_session)

        with pytest.raises(ValueError, match="Embedding vector"):
            upsert_rag_clause_embedding(
                sqlite_session,
                clause=clause,
                vector=vector,
                model="embed-model",
                input_hash=INPUT_HASH,
            )


class TestIsRagClauseEmbeddingStale:
    def test_returns_true_when_embedding_is_missing(self, sqlite_session) -> None:
        clause = _persisted_clause(sqlite_session)

        assert is_rag_clause_embedding_stale(
            clause,
            model="embed-model",
            input_hash=INPUT_HASH,
        )

    def test_returns_false_when_embedding_is_current(self, sqlite_session) -> None:
        clause = _persisted_clause(sqlite_session)
        upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="embed-model",
            input_hash=INPUT_HASH,
        )
        sqlite_session.expire(clause, ["rag_clause_embedding_rel"])

        assert not is_rag_clause_embedding_stale(
            clause,
            model="embed-model",
            input_hash=INPUT_HASH,
        )

    @pytest.mark.parametrize(
        ("model", "input_hash"),
        [
            ("new-model", INPUT_HASH),
            ("embed-model", "c" * 64),
        ],
    )
    def test_returns_true_when_model_or_input_changes(
        self,
        sqlite_session,
        model,
        input_hash,
    ) -> None:
        clause = _persisted_clause(sqlite_session)
        upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="embed-model",
            input_hash=INPUT_HASH,
        )
        sqlite_session.expire(clause, ["rag_clause_embedding_rel"])

        assert is_rag_clause_embedding_stale(
            clause,
            model=model,
            input_hash=input_hash,
        )

    def test_returns_true_when_dimensions_do_not_match_vector(
        self,
        sqlite_session,
    ) -> None:
        clause = _persisted_clause(sqlite_session)
        result = upsert_rag_clause_embedding(
            sqlite_session,
            clause=clause,
            vector=[1.0, 2.0],
            model="embed-model",
            input_hash=INPUT_HASH,
        )
        result.embedding.dimensions = 3
        sqlite_session.flush()
        sqlite_session.expire(clause, ["rag_clause_embedding_rel"])

        assert is_rag_clause_embedding_stale(
            clause,
            model="embed-model",
            input_hash=INPUT_HASH,
        )
