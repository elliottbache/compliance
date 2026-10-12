from copy import copy
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from compliance.db.models import RagClause, RagDocument
from compliance.llm.rag import embedding_input
from compliance.llm.rag.embedding_input import (
    build_clause_embedding_input,
    build_clause_embedding_input_hash,
    build_site_analysis_query_embedding_input,
)


def _document() -> RagDocument:
    return RagDocument(
        id=1,
        source_id="BOE-A-2018-16673",
        title="Organic Law 3/2018",
        source_kind="public_regulation",
        jurisdiction="Spain",
        effective_date=date(2018, 12, 5),
        updated_at=datetime(2026, 7, 20, 10, 24, 42, tzinfo=UTC),
        status="active",
        source_url="https://example.com/source",
    )


def _clause() -> RagClause:
    return RagClause(
        id=10,
        document_id=1,
        citation_ref="Artículo 1",
        title="Purpose",
        path_text="Título I. General provisions",
        text="Clause text.",
        content_hash="content-hash",
        sort_key="000001",
    )


class TestBuildSiteAnalysisQueryEmbeddingInput:
    def test_builds_one_labeled_query_per_finding(self) -> None:
        site = SimpleNamespace(city="Madrid", postal_code=28001)
        findings = [
            SimpleNamespace(
                finding_id=10,
                finding="Exit obstructed.",
                rule_index="4.2",
                rule_title="Emergency exits",
                rule_description="Exits must remain clear.",
            ),
            SimpleNamespace(
                finding_id=20,
                finding="Panel label missing.",
                rule_index="5.1",
                rule_title=None,
                rule_description="Panels must be labeled.",
            ),
        ]
        history = SimpleNamespace(
            certifications=[
                SimpleNamespace(
                    certifier_org_name="Example Certifier",
                    reg_title="Safety Standard",
                    reg_description="Workplace safety requirements.",
                    findings=findings,
                )
            ]
        )

        result = build_site_analysis_query_embedding_input(site, history)

        assert result == {
            10: (
                "Certifier: Example Certifier\n"
                "Site: Madrid 28001\n"
                "Regulation: Safety Standard\n"
                "Regulation text: Workplace safety requirements.\n"
                "Rule: 4.2 -- Emergency exits\n"
                "Rule text: Exits must remain clear.\n"
                "Finding: Exit obstructed."
            ),
            20: (
                "Certifier: Example Certifier\n"
                "Site: Madrid 28001\n"
                "Regulation: Safety Standard\n"
                "Regulation text: Workplace safety requirements.\n"
                "Rule: 5.1\n"
                "Rule text: Panels must be labeled.\n"
                "Finding: Panel label missing."
            ),
        }

    def test_returns_empty_mapping_without_findings(self) -> None:
        site = SimpleNamespace(city="Madrid", postal_code=28001)
        history = SimpleNamespace(certifications=[SimpleNamespace(findings=[])])

        assert build_site_analysis_query_embedding_input(site, history) == {}


class TestBuildClauseEmbeddingInput:
    def test_builds_labeled_retrieval_context(self) -> None:
        result = build_clause_embedding_input(_document(), _clause())

        assert result == (
            "Document title: Organic Law 3/2018\n"
            "Source ID: BOE-A-2018-16673\n"
            "Jurisdiction: Spain\n"
            "Path: Título I. General provisions\n"
            "Citation: Artículo 1\n"
            "Clause title: Purpose\n"
            "\n"
            "Text:\n"
            "Clause text."
        )

    def test_omits_absent_optional_fields(self) -> None:
        clause = _clause()
        clause.path_text = None
        clause.title = "  "

        result = build_clause_embedding_input(_document(), clause)

        assert "Path:" not in result
        assert "Clause title:" not in result
        assert "Citation: Artículo 1\n\nText:" in result

    def test_normalizes_whitespace(self) -> None:
        document = _document()
        document.title = "  Organic   Law 3/2018  "
        clause = _clause()
        clause.path_text = " Título I  \r\n  Capítulo I "
        clause.text = " First   line. \r\n Second line. "

        result = build_clause_embedding_input(document, clause)

        assert "Document title: Organic Law 3/2018" in result
        assert "Path: Título I\nCapítulo I" in result
        assert result.endswith("Text:\nFirst line.\nSecond line.")

    @pytest.mark.parametrize(
        ("target", "field", "message"),
        [
            ("document", "title", "document title"),
            ("document", "source_id", "document source ID"),
            ("document", "jurisdiction", "document jurisdiction"),
            ("clause", "citation_ref", "clause citation"),
            ("clause", "text", "clause text"),
        ],
    )
    def test_rejects_missing_required_semantic_fields(
        self,
        target,
        field,
        message,
    ) -> None:
        document = _document()
        clause = _clause()
        setattr(document if target == "document" else clause, field, "  ")

        with pytest.raises(ValueError, match=message):
            build_clause_embedding_input(document, clause)


class TestBuildClauseEmbeddingInputHash:
    def test_is_deterministic(self) -> None:
        first_hash = build_clause_embedding_input_hash(_document(), _clause())
        second_hash = build_clause_embedding_input_hash(_document(), _clause())

        assert first_hash == second_hash

    @pytest.mark.parametrize(
        ("target", "field", "value"),
        [
            ("document", "title", "Changed document title"),
            ("document", "source_id", "BOE-A-OTHER"),
            ("document", "jurisdiction", "European Union"),
            ("clause", "path_text", "Título II"),
            ("clause", "citation_ref", "Artículo 2"),
            ("clause", "title", "Changed clause title"),
            ("clause", "text", "Changed clause text."),
        ],
    )
    def test_changes_with_included_semantic_fields(
        self,
        target,
        field,
        value,
    ) -> None:
        document = _document()
        clause = _clause()
        original_hash = build_clause_embedding_input_hash(document, clause)
        setattr(document if target == "document" else clause, field, value)

        assert build_clause_embedding_input_hash(document, clause) != original_hash

    def test_changes_with_input_version(self, monkeypatch) -> None:
        original_hash = build_clause_embedding_input_hash(_document(), _clause())
        monkeypatch.setattr(embedding_input, "EMBEDDING_INPUT_VERSION", 2)

        assert (
            build_clause_embedding_input_hash(_document(), _clause()) != original_hash
        )

    def test_ignores_nonsemantic_metadata(self) -> None:
        document = copy(_document())
        clause = copy(_clause())
        original_hash = build_clause_embedding_input_hash(document, clause)

        document.id = 2
        document.source_kind = "changed-kind"
        document.effective_date = date(2020, 1, 1)
        document.updated_at = datetime(2026, 9, 29, tzinfo=UTC)
        document.status = "inactive"
        document.source_url = "https://example.com/changed"
        clause.id = 20
        clause.document_id = 2
        clause.content_hash = "changed-content-hash"
        clause.sort_key = "000002"

        assert build_clause_embedding_input_hash(document, clause) == original_hash
