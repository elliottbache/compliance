import json
from datetime import date
from unittest.mock import patch

import pytest

import compliance.llm.anthropic_api as anthropic_api
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
        self, site_history, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()

        with patch(
            "compliance.services.site_analysis.call_structured_model",
            return_value=site_analysis,
        ) as mock_call_structured_model:
            result = summarize_previous_visits(site_history)

        assert result == site_analysis
        assert mock_call_structured_model.call_args.kwargs["response_model"] is (
            SiteAnalysis
        )
        assert mock_call_structured_model.call_args.kwargs["ai_model"] == (
            anthropic_api._DEFAULT_AI_MODEL
        )

    def test_passes_provided_ai_model_and_case_info(
        self, site_history, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()

        with patch(
            "compliance.services.site_analysis.call_structured_model",
            return_value=site_analysis,
        ) as mock_call_structured_model:
            result = summarize_previous_visits(
                site_history,
                ai_model="claude-test",
                prompt_version="v-custom",
                case_info="case-1",
            )

        assert result == site_analysis
        assert mock_call_structured_model.call_args.kwargs["ai_model"] == "claude-test"
        assert (
            mock_call_structured_model.call_args.kwargs["prompt_version"] == "v-custom"
        )
        assert mock_call_structured_model.call_args.kwargs["case_info"] == "case-1"


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
