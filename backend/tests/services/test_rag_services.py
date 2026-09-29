from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import RagClause, RagClauseEmbedding, RagDocument
from compliance.services import rag
from compliance.services.rag import (
    import_rag_document_from_parsed_json as _import_rag_document_from_parsed_json,
)
from sqlalchemy import select


class _FakeEmbeddingProvider:
    model = "embed-test"

    def __init__(self) -> None:
        self.embed_text = MagicMock(return_value=[0.1, 0.2, 0.3])


def import_rag_document_from_parsed_json(
    session,
    document,
    *,
    embedding_provider=None,
):
    """Import with a deterministic provider for document-service tests."""
    return _import_rag_document_from_parsed_json(
        session,
        document,
        embedding_provider=embedding_provider or _FakeEmbeddingProvider(),
    )


def _parsed_document(**overrides) -> dict[str, object]:
    document = {
        "id": "BOE-A-2018-16673",
        "title": "Organic Law 3/2018",
        "source_kind": "public_regulation",
        "jurisdiction": "Spain",
        "effective_date": "2018-12-05",
        "updated_at": "2026-07-20T10:24:42Z",
        "status": "active",
        "url_eli": "https://www.boe.es/eli/es/lo/2018/12/05/3/con",
        "structure": [],
    }
    document.update(overrides)
    return document


def _article(number: str, text: str) -> dict[str, object]:
    return {
        "type": "article",
        "number": number,
        "text": text,
        "children": [],
    }


class TestImportRagDocumentFromParsedJson:
    def test_creates_new_rag_document(self, sqlite_session) -> None:
        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )

        persisted = sqlite_session.get(RagDocument, result.document.id)
        assert persisted is not None
        assert result.action == "created"
        assert persisted.source_id == "BOE-A-2018-16673"
        assert persisted.title == "Organic Law 3/2018"
        assert persisted.source_kind == "public_regulation"
        assert persisted.jurisdiction == "Spain"
        assert persisted.effective_date == date(2018, 12, 5)
        assert persisted.updated_at == datetime(2026, 7, 20, 10, 24, 42)
        assert persisted.status == "active"
        assert persisted.source_url == "https://www.boe.es/eli/es/lo/2018/12/05/3/con"

    def test_creates_extracted_clauses_for_new_document(self, sqlite_session) -> None:
        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                structure=[
                    _article("1", "First clause."),
                    _article("2", "Second clause."),
                ]
            ),
        )

        clauses = list(
            sqlite_session.scalars(select(RagClause).order_by(RagClause.sort_key))
        )
        assert result.clauses_created == 2
        assert [clause.document_id for clause in clauses] == [
            result.document.id,
            result.document.id,
        ]
        assert [clause.citation_ref for clause in clauses] == [
            "Artículo 1",
            "Artículo 2",
        ]
        assert [clause.text for clause in clauses] == [
            "First clause.",
            "Second clause.",
        ]

    def test_creates_embeddings_for_extracted_clauses(self, sqlite_session) -> None:
        provider = _FakeEmbeddingProvider()

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
            embedding_provider=provider,
        )

        embedding = sqlite_session.scalar(select(RagClauseEmbedding))
        assert result.embeddings_created == 1
        assert result.embeddings_updated == 0
        assert result.embeddings_unchanged == 0
        assert embedding is not None
        assert embedding.embedding == [0.1, 0.2, 0.3]
        assert embedding.embedding_model == "embed-test"
        provider.embed_text.assert_called_once()

    def test_skipped_document_does_not_regenerate_current_embeddings(
        self,
        sqlite_session,
    ) -> None:
        provider = _FakeEmbeddingProvider()
        import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
            embedding_provider=provider,
        )
        provider.embed_text.reset_mock()

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
            embedding_provider=provider,
        )

        assert result.action == "skipped"
        assert result.embeddings_unchanged == 1
        provider.embed_text.assert_not_called()

    def test_skipped_document_backfills_missing_embeddings(
        self,
        sqlite_session,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
        )
        embedding = sqlite_session.scalar(select(RagClauseEmbedding))
        sqlite_session.delete(embedding)
        sqlite_session.commit()
        provider = _FakeEmbeddingProvider()

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                title="Must not replace the stored title",
                structure=[_article("1", "Incoming text must be ignored.")],
            ),
            embedding_provider=provider,
        )

        assert result.action == "skipped"
        assert result.document.id == original.document.id
        assert result.document.title == "Organic Law 3/2018"
        assert result.embeddings_created == 1
        embedding_input = provider.embed_text.call_args.args[0]
        assert "First clause." in embedding_input
        assert "Incoming text must be ignored." not in embedding_input

    def test_refreshes_embedding_when_model_changes(self, sqlite_session) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
        )
        original_embedding = sqlite_session.scalar(select(RagClauseEmbedding))
        original_embedding_id = original_embedding.id
        provider = _FakeEmbeddingProvider()
        provider.model = "new-embed-model"

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
            embedding_provider=provider,
        )

        refreshed = sqlite_session.scalar(select(RagClauseEmbedding))
        assert result.action == "skipped"
        assert result.document.id == original.document.id
        assert result.embeddings_updated == 1
        assert refreshed.id == original_embedding_id
        assert refreshed.embedding_model == "new-embed-model"

    def test_refreshes_only_embeddings_with_changed_input(
        self,
        sqlite_session,
    ) -> None:
        import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                structure=[
                    _article("1", "Original first clause."),
                    _article("2", "Unchanged second clause."),
                ]
            ),
        )
        provider = _FakeEmbeddingProvider()

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                updated_at="2026-07-21T10:24:42Z",
                structure=[
                    _article("1", "Changed first clause."),
                    _article("2", "Unchanged second clause."),
                ],
            ),
            embedding_provider=provider,
        )

        assert result.action == "updated"
        assert result.embeddings_updated == 1
        assert result.embeddings_unchanged == 1
        provider.embed_text.assert_called_once()
        assert "Changed first clause." in provider.embed_text.call_args.args[0]

    def test_rolls_back_document_clause_and_embedding_when_embedding_fails(
        self,
        sqlite_session,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "Original text.")]),
        )
        original_embedding = sqlite_session.scalar(select(RagClauseEmbedding))
        original_hash = original_embedding.input_hash
        provider = _FakeEmbeddingProvider()
        provider.embed_text.side_effect = RuntimeError("Embedding failed.")

        with pytest.raises(RuntimeError, match="Embedding failed"):
            import_rag_document_from_parsed_json(
                sqlite_session,
                _parsed_document(
                    title="Must be rolled back",
                    updated_at="2026-07-21T10:24:42Z",
                    structure=[_article("1", "Changed text.")],
                ),
                embedding_provider=provider,
            )

        sqlite_session.refresh(original.document)
        persisted_clause = sqlite_session.scalar(select(RagClause))
        persisted_embedding = sqlite_session.scalar(select(RagClauseEmbedding))
        assert original.document.title == "Organic Law 3/2018"
        assert persisted_clause.text == "Original text."
        assert persisted_embedding.input_hash == original_hash

    def test_updates_existing_rag_document_with_same_source_id(
        self,
        sqlite_session,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                title="Updated title",
                updated_at="2026-07-21T10:24:42Z",
                status="superseded",
                source_url="https://example.com/source",
            ),
        )

        assert result.action == "updated"
        assert result.document.id == original.document.id
        assert result.document.title == "Updated title"
        assert result.document.status == "superseded"
        assert result.document.source_url == "https://example.com/source"
        assert sqlite_session.query(RagDocument).count() == 1

    @pytest.mark.parametrize(
        "incoming_updated_at",
        [
            "2026-07-20T10:24:42Z",
            "2026-07-19T10:24:42Z",
        ],
    )
    def test_skips_when_incoming_updated_at_is_not_newer(
        self,
        sqlite_session,
        monkeypatch,
        incoming_updated_at,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )
        commit = MagicMock()
        extract = MagicMock()
        monkeypatch.setattr(sqlite_session, "commit", commit)
        monkeypatch.setattr(rag, "import_rag_clauses", extract)

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                title="Must not replace the stored title",
                updated_at=incoming_updated_at,
            ),
        )

        assert result.action == "skipped"
        assert result.document.id == original.document.id
        assert result.document.title == "Organic Law 3/2018"
        commit.assert_not_called()
        extract.assert_not_called()

    def test_preserves_clause_ids_when_tree_positions_move(
        self,
        sqlite_session,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                structure=[
                    _article("1", "First clause."),
                    _article("2", "Second clause."),
                ]
            ),
        )
        original_ids = {
            clause.citation_ref: clause.id
            for clause in sqlite_session.scalars(
                select(RagClause).where(RagClause.document_id == original.document.id)
            )
        }

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                updated_at="2026-07-21T10:24:42Z",
                structure=[
                    _article("2", "Second clause."),
                    _article("1", "First clause."),
                ],
            ),
        )
        moved_clauses = list(
            sqlite_session.scalars(
                select(RagClause)
                .where(RagClause.document_id == result.document.id)
                .order_by(RagClause.sort_key)
            )
        )

        assert result.clauses_updated == 2
        assert [clause.id for clause in moved_clauses] == [
            original_ids["Artículo 2"],
            original_ids["Artículo 1"],
        ]

    def test_updates_clause_at_same_tree_position(self, sqlite_session) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "Original text.")]),
        )
        original_clause = sqlite_session.scalar(
            select(RagClause).where(RagClause.document_id == original.document.id)
        )

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                updated_at="2026-07-21T10:24:42Z",
                structure=[_article("1", "Changed text.")],
            ),
        )
        updated_clause = sqlite_session.scalar(
            select(RagClause).where(RagClause.document_id == result.document.id)
        )

        assert original_clause is not None
        assert updated_clause is not None
        assert result.clauses_updated == 1
        assert updated_clause.id == original_clause.id
        assert updated_clause.text == "Changed text."

    def test_inserts_and_deletes_clauses(self, sqlite_session) -> None:
        import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "First clause.")]),
        )

        appended = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                updated_at="2026-07-21T10:24:42Z",
                structure=[
                    _article("1", "First clause."),
                    _article("2", "Second clause."),
                ],
            ),
        )
        emptied = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                updated_at="2026-07-22T10:24:42Z",
                structure=[],
            ),
        )

        assert appended.clauses_created == 1
        assert appended.clauses_unchanged == 1
        assert emptied.clauses_deleted == 2
        assert sqlite_session.query(RagClause).count() == 0

    def test_rolls_back_document_and_clauses_if_extraction_fails(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "Original text.")]),
        )
        monkeypatch.setattr(
            rag,
            "import_rag_clauses",
            MagicMock(side_effect=ValueError("Extraction failed.")),
        )

        with pytest.raises(ValueError, match="Extraction failed"):
            import_rag_document_from_parsed_json(
                sqlite_session,
                _parsed_document(
                    title="Must be rolled back",
                    updated_at="2026-07-21T10:24:42Z",
                ),
            )

        sqlite_session.refresh(original.document)
        persisted_clause = sqlite_session.scalar(
            select(RagClause).where(RagClause.document_id == original.document.id)
        )
        assert original.document.title == "Organic Law 3/2018"
        assert persisted_clause is not None
        assert persisted_clause.text == "Original text."

    def test_rolls_back_document_if_clause_synchronization_fails(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        original = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(structure=[_article("1", "Original text.")]),
        )
        monkeypatch.setattr(
            rag,
            "_sync_rag_clauses",
            MagicMock(side_effect=ValueError("Clause synchronization failed.")),
        )

        with pytest.raises(ValueError, match="Clause synchronization failed"):
            import_rag_document_from_parsed_json(
                sqlite_session,
                _parsed_document(
                    title="Must be rolled back",
                    updated_at="2026-07-21T10:24:42Z",
                    structure=[_article("1", "Changed text.")],
                ),
            )

        sqlite_session.refresh(original.document)
        assert original.document.title == "Organic Law 3/2018"
        assert original.document.updated_at == datetime(2026, 7, 20, 10, 24, 42)

    def test_rejects_duplicate_extracted_content_hashes(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        duplicate_clause = {
            "document_source_id": "BOE-A-2018-16673",
            "citation_ref": "Artículo 1",
            "title": None,
            "path_text": "",
            "text": "Duplicate text.",
            "content_hash": "same-hash",
            "sort_key": "000001",
        }
        monkeypatch.setattr(
            rag,
            "import_rag_clauses",
            MagicMock(
                return_value=[
                    duplicate_clause,
                    {**duplicate_clause, "sort_key": "000002"},
                ]
            ),
        )

        with pytest.raises(ValueError, match="duplicate content hashes"):
            import_rag_document_from_parsed_json(
                sqlite_session,
                _parsed_document(),
            )

        assert sqlite_session.query(RagDocument).count() == 0

    def test_rejects_duplicate_extracted_sort_keys(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        clause = {
            "document_source_id": "BOE-A-2018-16673",
            "citation_ref": "Artículo 1",
            "title": None,
            "path_text": "",
            "text": "First text.",
            "content_hash": "first-hash",
            "sort_key": "000001",
        }
        monkeypatch.setattr(
            rag,
            "import_rag_clauses",
            MagicMock(
                return_value=[
                    clause,
                    {
                        **clause,
                        "text": "Second text.",
                        "content_hash": "second-hash",
                    },
                ]
            ),
        )

        with pytest.raises(ValueError, match="duplicate sort keys"):
            import_rag_document_from_parsed_json(
                sqlite_session,
                _parsed_document(),
            )

        assert sqlite_session.query(RagDocument).count() == 0

    def test_uses_effective_date_for_freshness_when_updated_at_is_missing(
        self,
        sqlite_session,
    ) -> None:
        import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(updated_at=None, effective_date="2018-12-05"),
        )

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                title="Updated title",
                updated_at=None,
                effective_date="2018-12-06",
            ),
        )

        assert result.action == "updated"
        assert result.document.title == "Updated title"

    def test_uses_updated_at_date_when_effective_date_is_missing(
        self,
        sqlite_session,
    ) -> None:
        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(effective_date=None),
        )

        assert result.document.effective_date == date(2026, 7, 20)

    def test_uses_today_when_both_dates_are_missing(
        self,
        sqlite_session,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(rag, "_today_utc", lambda: date(2026, 9, 29))

        result = import_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(updated_at=None, effective_date=None),
        )

        assert result.action == "created"
        assert result.document.updated_at is None
        assert result.document.effective_date == date(2026, 9, 29)

    def test_raises_value_error_without_committing_when_required_metadata_is_missing(
        self,
    ) -> None:
        session = MagicMock()

        with pytest.raises(ValueError, match="requires title"):
            import_rag_document_from_parsed_json(
                session,
                _parsed_document(title=" "),
            )

        session.execute.assert_not_called()
        session.add.assert_not_called()
        session.commit.assert_not_called()
