import json
from pathlib import Path

import pytest
from rag_eval_support import CORPUS_PATH, load_corpus, load_rag_context


class TestLoadCorpus:
    def test_loads_unique_shared_corpus(self) -> None:
        corpus = load_corpus()

        citations = {
            clause.citation_ref
            for document in corpus.documents
            for clause in document.clauses
        }
        assert {"WS-1", "DP-1", "IS-1", "SR-1"} <= citations

    def test_rejects_duplicate_citations(self, tmp_path: Path) -> None:
        payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
        payload["documents"][1]["clauses"][0]["citation_ref"] = "WS-1"
        corpus_path = tmp_path / "corpus.json"
        corpus_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="Duplicate clause citations"):
            load_corpus(corpus_path)


class TestLoadRagContext:
    def test_resolves_citation_to_top_clause(self, tmp_path: Path) -> None:
        (tmp_path / "input_rag_context.json").write_text(
            json.dumps({"citations_by_finding": {"10": ["WS-1"]}}),
            encoding="utf-8",
        )

        context = load_rag_context(tmp_path, load_corpus(), finding_ids={10})

        assert len(context) == 1
        assert context[0].finding_id == 10
        assert context[0].rag_clause.citation_ref == "WS-1"

    def test_rejects_unknown_citation(self, tmp_path: Path) -> None:
        (tmp_path / "input_rag_context.json").write_text(
            json.dumps({"citations_by_finding": {"10": ["UNKNOWN"]}}),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Unknown RAG context citations"):
            load_rag_context(tmp_path, load_corpus(), finding_ids={10})


def test_all_eval_cases_have_valid_rag_context() -> None:
    cases_path = Path(__file__).parent / "evals/site_history_cases"
    corpus = load_corpus()

    for case_path in (path for path in cases_path.iterdir() if path.is_dir()):
        history_payload = json.loads(
            (case_path / "input_site_history.json").read_text(encoding="utf-8")
        )
        finding_ids = {
            finding["finding_id"]
            for certification in history_payload["certifications"]
            for finding in certification["findings"]
        }
        load_rag_context(case_path, corpus, finding_ids=finding_ids)
