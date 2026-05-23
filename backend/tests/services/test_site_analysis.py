import json
from datetime import date
from unittest.mock import patch

import compliance.llm.anthropic_api as anthropic_api
import pytest
from compliance.llm.schemas import (
    SiteAnalysis,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory
from compliance.services.site_analysis import (
    _build_site_analysis_system_prompt,
    _build_site_analysis_user_message,
    summarize_previous_visits,
)


@pytest.fixture
def site_history() -> SiteHistory:
    return SiteHistory(
        site_id=71,
        inspection_count=1,
        latest_inspection_date=date(2024, 1, 10),
        certifications=[
            CertificationHistory(
                cert_id=100,
                result="pass",
                resolution_date=date(2024, 1, 20),
                reg_title="USDA Organic",
                reg_description="Organic certification",
                certifier_org_name="Org A",
                inspection_date=date(2024, 1, 10),
                findings=[
                    FindingHistory(
                        finding_id=1,
                        finding="Issue A",
                        rule_index="7 CFR 205.201",
                        rule_title="Rule A",
                        rule_description="Rule description A",
                    )
                ],
            )
        ],
    )


class TestSummarizePreviousVisits:
    def test_builds_site_analysis_prompt_and_calls_structured_model(
        self, monkeypatch, site_history, site_analysis_factory
    ) -> None:
        monkeypatch.setenv("AI_MODE", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        site_analysis = site_analysis_factory()

        with patch(
            "compliance.services.site_analysis.call_model",
            return_value=site_analysis,
        ) as mock_call_model:
            result = summarize_previous_visits(site_history)

        assert result == site_analysis
        assert mock_call_model.call_args.kwargs["response_model"] is SiteAnalysis
        assert mock_call_model.call_args.kwargs["ai_model"] == (
            anthropic_api._DEFAULT_AI_MODEL
        )

    def test_passes_provided_ai_model_and_case_info(
        self, monkeypatch, site_history, site_analysis_factory
    ) -> None:
        monkeypatch.setenv("AI_MODE", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        site_analysis = site_analysis_factory()

        with patch(
            "compliance.services.site_analysis.call_model",
            return_value=site_analysis,
        ) as mock_call_model:
            result = summarize_previous_visits(
                site_history,
                ai_model="claude-test",
                prompt_version="v-custom",
                case_info="case-1",
            )

        assert result == site_analysis
        assert mock_call_model.call_args.kwargs["ai_model"] == "claude-test"
        assert mock_call_model.call_args.kwargs["prompt_version"] == "v-custom"
        assert mock_call_model.call_args.kwargs["case_info"] == "case-1"

    def test_returns_mock_analysis_by_default(self, monkeypatch, site_history) -> None:
        monkeypatch.delenv("AI_MODE", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with patch("compliance.services.site_analysis.call_model") as mock_call_model:
            result = summarize_previous_visits(site_history)

        assert result.site_id == 71
        assert result.inspection_count == 1
        assert "Mock AI analysis" in result.executive_summary
        assert result.recurring_issues == []
        assert result.missing_information == []
        assert result.needs_human_review == []
        assert result.suggestions == []
        mock_call_model.assert_not_called()

    def test_raises_for_unsupported_ai_mode(self, monkeypatch, site_history) -> None:
        monkeypatch.setenv("AI_MODE", "local")

        with pytest.raises(ValueError, match="Unsupported AI_MODE: local"):
            summarize_previous_visits(site_history)

    def test_requires_api_key_for_anthropic_mode(
        self, monkeypatch, site_history
    ) -> None:
        monkeypatch.setenv("AI_MODE", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is required"):
            summarize_previous_visits(site_history)


class TestBuildSiteAnalysisPrompts:
    def test_system_prompt_contains_analysis_boundaries(self) -> None:
        result = _build_site_analysis_system_prompt()

        assert "Use only the facts provided" in result
        assert "Do not make compliance decisions" in result

    def test_user_message_serializes_site_history(self, site_history) -> None:
        result = _build_site_analysis_user_message(site_history)

        assert "Analyze the following site history" in result
        assert (
            json.dumps(site_history.model_dump(mode="json"), separators=(",", ":"))[:40]
            in result
        )
