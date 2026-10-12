"""Fixture loading for deterministic RAG context in LLM evaluations."""

from pathlib import Path

from compliance.services.rag_embeddings import RagClausePublicSchema, TopClause
from pydantic import BaseModel, ConfigDict, Field

CORPUS_PATH = Path(__file__).parent / "evals/rag_corpus.json"
RAG_CONTEXT_FILE = Path("input_rag_context.json")


class EvalClause(BaseModel):
    """One clause in the shared evaluation corpus."""

    model_config = ConfigDict(frozen=True)

    citation_ref: str
    title: str
    path_text: str | None = None
    text: str


class EvalDocument(BaseModel):
    """One document in the shared evaluation corpus."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    title: str
    clauses: list[EvalClause] = Field(min_length=1)


class EvalCorpus(BaseModel):
    """Shared synthetic documents used by the LLM evaluations."""

    model_config = ConfigDict(frozen=True)

    documents: list[EvalDocument] = Field(min_length=1)


class EvalRagContext(BaseModel):
    """Citation references to inject for each finding in one eval case."""

    model_config = ConfigDict(frozen=True)

    citations_by_finding: dict[int, list[str]]


def load_corpus(path: Path = CORPUS_PATH) -> EvalCorpus:
    """Load the corpus and reject duplicate IDs or citations."""
    corpus = EvalCorpus.model_validate_json(path.read_text(encoding="utf-8"))
    _reject_duplicates(
        [
            clause.citation_ref
            for document in corpus.documents
            for clause in document.clauses
        ],
        "clause citation",
    )
    return corpus


def load_rag_context(
    case_path: Path, corpus: EvalCorpus, *, finding_ids: set[int]
) -> list[TopClause]:
    """Resolve one case's citation references into prompt-ready clauses."""
    context = EvalRagContext.model_validate_json(
        (case_path / RAG_CONTEXT_FILE).read_text(encoding="utf-8")
    )
    context_finding_ids = set(context.citations_by_finding)
    if context_finding_ids != finding_ids:
        raise ValueError(
            f"RAG context for {case_path.name!r} must map exactly the finding IDs "
            f"{sorted(finding_ids)}; received {sorted(context_finding_ids)}."
        )
    clauses = {}
    clause_id = 0
    for document_id, document in enumerate(corpus.documents, start=1):
        for clause in document.clauses:
            clause_id += 1
            clauses[clause.citation_ref] = (document_id, clause_id, clause)
    requested = {
        citation
        for citations in context.citations_by_finding.values()
        for citation in citations
    }
    unknown = requested - set(clauses)
    if unknown:
        raise ValueError(f"Unknown RAG context citations: {sorted(unknown)}.")

    return [
        TopClause(
            finding_id=finding_id,
            rag_clause=RagClausePublicSchema(
                id=clauses[citation][1],
                document_id=clauses[citation][0],
                citation_ref=citation,
                title=clauses[citation][2].title,
                path_text=clauses[citation][2].path_text,
                text=clauses[citation][2].text,
            ),
        )
        for finding_id, citations in context.citations_by_finding.items()
        for citation in citations
    ]


def _reject_duplicates(values: list[int] | list[str], label: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate {label}s: {duplicates}.")
