from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import RagDocument
from compliance.services.rag import upsert_rag_document_from_parsed_json


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


class TestUpsertRagDocumentFromParsedJson:
    def test_creates_new_rag_document(self, sqlite_session) -> None:
        result = upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )

        persisted = sqlite_session.get(RagDocument, result.id)
        assert persisted is not None
        assert persisted.source_id == "BOE-A-2018-16673"
        assert persisted.title == "Organic Law 3/2018"
        assert persisted.source_kind == "public_regulation"
        assert persisted.jurisdiction == "Spain"
        assert persisted.effective_date == date(2018, 12, 5)
        assert persisted.updated_at == datetime(2026, 7, 20, 10, 24, 42)
        assert persisted.status == "active"
        assert persisted.source_url == "https://www.boe.es/eli/es/lo/2018/12/05/3/con"

    def test_updates_existing_rag_document_with_same_source_id(
        self,
        sqlite_session,
    ) -> None:
        original = upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )

        result = upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(
                title="Updated title",
                status="superseded",
                source_url="https://example.com/source",
            ),
        )

        assert result.id == original.id
        assert result.title == "Updated title"
        assert result.status == "superseded"
        assert result.source_url == "https://example.com/source"
        assert sqlite_session.query(RagDocument).count() == 1

    def test_uses_updated_at_date_when_effective_date_is_missing(
        self,
        sqlite_session,
    ) -> None:
        result = upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(effective_date=None),
        )

        assert result.effective_date == date(2026, 7, 20)

    def test_raises_value_error_without_committing_when_required_metadata_is_missing(
        self,
    ) -> None:
        session = MagicMock()

        with pytest.raises(ValueError, match="requires title"):
            upsert_rag_document_from_parsed_json(
                session,
                _parsed_document(title=" "),
            )

        session.execute.assert_not_called()
        session.add.assert_not_called()
        session.commit.assert_not_called()
