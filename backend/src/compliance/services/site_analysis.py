"""Site-history analysis service with mock and live AI provider modes."""

import json
import logging
from typing import Protocol

from compliance.config import Settings, settings
from compliance.db.models import Site
from compliance.llm.anthropic_api import AnthropicAIProvider
from compliance.llm.qwen_api import QwenAIProvider
from compliance.llm.rag.embedding_input import build_site_analysis_query_embedding_input
from compliance.llm.rag.ollama_embeddings import OllamaEmbeddingProvider
from compliance.llm.schemas import SiteAnalysis
from compliance.schemas import SiteHistory
from compliance.services.rag_embeddings import (
    RagClausePublicSchema,
    TopClause,
    embed_rag_queries,
    find_top_embeddings,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AIProvider(Protocol):
    """Protocol implemented by structured-output AI provider adapters."""

    def call_model[
        T: BaseModel
    ](
        self,
        system_context: str,
        user_message: str,
        *,
        response_model: type[T],
        ai_model: str,
        prompt_version: str,
        case_info: str = "",
    ) -> T: ...


def summarize_previous_visits(
    *,
    session: Session,
    site: Site,
    site_history: SiteHistory,
    ai_model: str | None = None,
    prompt_version: str = "v1.3",
    case_info: str = "",
) -> SiteAnalysis:
    """Analyze site history with the site-analysis prompt workflow.

    This service owns the site-specific system prompt and user message, then
    delegates the generic structured-output call to the LLM adapter. The adapter
    returns a validated SiteAnalysis.

    Args:
        site_history: Site history data to summarize and analyze.
        ai_model: Optional model override. Defaults to the configured AI_MODEL
            for the active provider.
        prompt_version: Version label for the site-analysis prompt.
        case_info: Optional metadata or identifier for the current case,
            used primarily for error logging. Defaults to an empty string.

    Returns:
        The validated structured output containing the summary, recurring
        issues, missing information, review items, and suggestions.

    Raises:
        ValidationError: If the model output cannot be parsed into a
            SiteAnalysis object even after a retry.
        json.JSONDecodeError: If the model returns invalid JSON that cannot
            be recovered.
    """
    ai_mode = settings.ai_mode

    if ai_mode == "mock":
        return _mock_site_analysis(site_history)

    if ai_mode not in {"anthropic", "local"}:
        raise ValueError(f"Unsupported AI_MODE: {ai_mode}")

    if ai_mode == "anthropic" and not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required when AI_MODE=anthropic.")

    ai_provider = _build_ai_provider(settings)
    selected_ai_model = ai_model or settings.ai_model
    if selected_ai_model is None:
        raise RuntimeError("AI_MODEL is required when AI_MODE is not mock.")

    system_context = _build_site_analysis_system_prompt()

    # retrieve RAG embeddings: create function in this module to retrieve embeddings and create one str
    embedded_context = _retrieve_site_analysis_rag_clauses(
        session=session, site=site, site_history=site_history
    )

    user_message = _build_site_analysis_user_message(
        site_history=site_history, embedded_context=embedded_context
    )

    return ai_provider.call_model(
        system_context,
        user_message,
        response_model=SiteAnalysis,
        ai_model=selected_ai_model,
        prompt_version=prompt_version,
        case_info=case_info,
    )


def _build_ai_provider(settings: Settings) -> AIProvider:
    """Return the configured live AI provider adapter."""
    if settings.ai_mode == "anthropic":
        return AnthropicAIProvider()
    elif settings.ai_mode == "local":
        return QwenAIProvider()

    raise ValueError(f"Unsupported AI_MODE: {settings.ai_mode}")


def _mock_site_analysis(site_history: SiteHistory) -> SiteAnalysis:
    """Return deterministic site analysis for offline demos and tests."""
    return SiteAnalysis(
        site_id=site_history.site_id,
        inspection_count=site_history.inspection_count,
        executive_summary=(
            "Mock AI analysis: this site history was loaded successfully. "
            "Use AI_MODE=anthropic with an Anthropic API key for live analysis."
        ),
        recurring_issues=[],
        missing_information=[],
        needs_human_review=[],
        suggestions=[],
    )


def _build_site_analysis_system_prompt() -> str:
    """Build the system prompt that defines the site-analysis guardrails."""
    return """You are assisting with inspection-history analysis for an 
    inspector.
    
    Use only the facts provided.
    Do not invent missing facts.
    If something is unclear or absent, put it in missing_information.
    Do not make compliance decisions or legal judgments.
    You can make suggestions, but make sure it is stated that they are only suggestions.
    Return output that matches the requested schema exactly."""


def _retrieve_site_analysis_rag_clauses(
    *, session: Session, site: Site, site_history: SiteHistory
) -> list[TopClause]:
    """Retrieve embedded clauses that are closest to the input findings."""
    # create list of findings
    finding_queries = build_site_analysis_query_embedding_input(site, site_history)
    embedding_provider = OllamaEmbeddingProvider()

    # transform into vectors
    finding_embeddings = embed_rag_queries(
        queries=finding_queries, provider=embedding_provider
    )

    # search RAG embeddings for closest 3 vectors for each and retrieve text from top 8 vectors
    top_embeddings = find_top_embeddings(
        session=session,
        query_embeddings=finding_embeddings,
        provider=embedding_provider,
    )

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

    return closest_clauses


def _build_site_analysis_user_message(
    site_history: SiteHistory, embedded_context: list[TopClause]
) -> str:
    """Build the user prompt containing instructions and serialized site history."""
    user_message = """Analyze the following site history.
    
    Goal:
    - write a concise factual summary
    - identify recurring issues only when supported by repeated findings/history
    - list missing information
    - list reasons a human should review
    - make a suggestion of things an inspector should pay attention to during a visit based 
    on previous visits and regulation and rule descriptions.
    
    Field guidance:
    - executive_summary: short factual overview
    - recurring_issues: repeated problems supported by the history.  Only repeated issues 
    supported by more than one certification or repeated rule/finding pattern.  Requires
    at least 2 evidence references.
    - missing_information: facts that are absent or unclear.  If a data field has an 
    empty list or dict, None or null, verify if this makes sense.  If it doesn't, 
    missing_information should document it.  Do not place missing information in the 
    executive_summary.  Do not add things that do not directly affect the validity or confidence
    in the certification. Missing findings belong in missing_information.
    - needs_human_review: places where a person should verify or interpret.  Be sure to 
    cite the regulation title, rule index and rule title if available.  Should name ambiguity 
    or interpretation boundary, not just "review this".  Do not question the validity of
    the inspector's conclusions.
    - suggestions: suggestions for preparing for the visit and for 
    during the visit.  Must be framed as preparation suggestions, not conclusions.  Must 
    be tied to the provided findings/regulations/rules.
    - For all of these except executive_summary, attach a reference to the piece(s) of evidence.
    Attach a reference to the certification and possibly finding, rule, or regulation if they apply.
    
    General:
    - Maintenance records are not available nor will they ever be.
    - Corrective actions are also not available.
    - Resolution dates can acceptably be null if the status is "In progress" or "Fail".
    They should not be null for "Pass".
    - Pass grades do not require findings.  Fail grades do.
    - Findings are tied to a rule, which is tied to a regulation, which is tied to a certification
    for a specific site history.  The finding ID cited in evidence must coincide with the cited
    certification.
    
    Site history:
    """
    user_message += json.dumps(
        site_history.model_dump(mode="json"), separators=(",", ":")
    )

    if embedded_context:
        user_message += (
            "\n\n<relevant_rag_clauses>\n"
            "The following retrieved clauses may be relevant to the cited findings. "
            "Treat them as supporting context, not as conclusions.\n"
        )
        user_message += json.dumps(
            [clause.model_dump(mode="json") for clause in embedded_context],
            ensure_ascii=False,
            indent=2,
        )
        user_message += "\n</relevant_rag_clauses>"

    return user_message


if __name__ == "__main__":
    from datetime import date

    from compliance.db.db_access import get_engine
    from compliance.schemas import CertificationHistory, FindingHistory

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
        inspection_count=2,
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
                inspection_date=date(2025, 9, 10),
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
                ],
            ),
            CertificationHistory(
                cert_id=202,
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
                        finding_id=302,
                        finding=(
                            "Boxes were stored in front of an emergency exit, "
                            "restricting access."
                        ),
                        rule_index="4.2",
                        rule_title="Emergency exits",
                        rule_description=(
                            "Emergency exits must remain clear and accessible."
                        ),
                    ),
                    FindingHistory(
                        finding_id=303,
                        finding=(
                            "The inspection record for one fire extinguisher "
                            "was not available."
                        ),
                        rule_index="5.1",
                        rule_title="Fire-protection equipment",
                        rule_description=(
                            "Fire-protection equipment must be inspected and "
                            "documented at the required intervals."
                        ),
                    ),
                ],
            ),
        ],
    )

    with Session(get_engine()) as session:
        analysis = summarize_previous_visits(
            session=session,
            site=sample_site,
            site_history=sample_site_history,
            case_info="temporary-site-analysis-entrypoint",
        )

    print(analysis.model_dump_json(indent=2))
