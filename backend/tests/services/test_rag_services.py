from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from compliance.db.models import RagDocument
from compliance.services import rag
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
        original = upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(),
        )
        commit = MagicMock()
        monkeypatch.setattr(sqlite_session, "commit", commit)

        result = upsert_rag_document_from_parsed_json(
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

    def test_uses_effective_date_for_freshness_when_updated_at_is_missing(
        self,
        sqlite_session,
    ) -> None:
        upsert_rag_document_from_parsed_json(
            sqlite_session,
            _parsed_document(updated_at=None, effective_date="2018-12-05"),
        )

        result = upsert_rag_document_from_parsed_json(
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
        result = upsert_rag_document_from_parsed_json(
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

        result = upsert_rag_document_from_parsed_json(
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
            upsert_rag_document_from_parsed_json(
                session,
                _parsed_document(title=" "),
            )

        session.execute.assert_not_called()
        session.add.assert_not_called()
        session.commit.assert_not_called()
