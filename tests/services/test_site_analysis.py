import json
from datetime import date
from unittest.mock import patch

import pytest

import compliance.llm.anthropic_api as anthropic_api
from compliance.llm.schemas import (
    EvidenceRef,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import CertificationHistory, FindingHistory, SiteHistory
from compliance.services.site_analysis import (
    _beautify_attr_name,
    _build_site_analysis_system_prompt,
    _build_site_analysis_user_message,
    _format_evidence_item_to_markdown,
    _render_site_analysis_attribute,
    render_site_analysis_markdown,
    summarize_previous_visits,
)


@pytest.fixture
def evidence_ref_factory():
    def _build(**overrides) -> EvidenceRef:
        data = {
            "cert_id": 100,
            "reg_title": "USDA Organic",
            "finding_id": 1,
            "rule_index": "7 CFR 205.201",
            "inspection_date": date(2024, 1, 10),
            "support_text": "Inspector noted labeling issue.",
        }
        data.update(overrides)
        return EvidenceRef(**data)

    return _build


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


@pytest.fixture
def site_analysis_factory(evidence_ref_factory):
    def _build(**overrides) -> SiteAnalysis:
        recurring_evidence_1 = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Recurring evidence 1.",
        )
        recurring_evidence_2 = evidence_ref_factory(
            cert_id=100,
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="Recurring evidence 2.",
        )
        missing_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="Missing info evidence.",
        )
        human_review_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Needs review evidence.",
        )
        suggestion_evidence = evidence_ref_factory(
            cert_id=100,
            finding_id=1,
            rule_index="7 CFR 205.201",
            support_text="Suggestion evidence.",
        )

        data = {
            "site_id": 71,
            "inspection_count": 1,
            "executive_summary": "Short summary.",
            "recurring_issues": [
                RecurringIssueItem(
                    item="Repeated labeling issue",
                    confidence_note="Seen across inspections.",
                    evidence=[recurring_evidence_1, recurring_evidence_2],
                )
            ],
            "missing_information": [
                MissingInfoItem(
                    item="Missing attachments",
                    why_missing_matters="They would confirm follow-up details.",
                    evidence=[missing_evidence],
                )
            ],
            "needs_human_review": [
                HumanReviewItem(
                    item="Inspector should review ambiguity",
                    evidence=[human_review_evidence],
                )
            ],
            "suggestions": [
                SuggestionItem(
                    item="Check labeling records",
                    basis="Prior labeling issue suggests targeted follow-up.",
                    evidence=[suggestion_evidence],
                )
            ],
        }
        data.update(overrides)
        return SiteAnalysis(**data)

    return _build


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


class TestRenderSiteAnalysisMarkdown:
    def test_renders_full_markdown_document(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = render_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Executive summary\nShort summary."
        )
        assert "## Recurring issues" in result
        assert "## Missing information" in result
        assert "## Needs human review" in result
        assert "## Suggestions" in result

    def test_renders_empty_executive_summary(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory(executive_summary="")

        result = render_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Executive summary\nNone.\n## Recurring issues"
        )

    def test_renders_sections_in_expected_order(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = render_site_analysis_markdown(site_analysis)

        recurring_idx = result.index("## Recurring issues")
        missing_idx = result.index("## Missing information")
        human_idx = result.index("## Needs human review")
        suggestions_idx = result.index("## Suggestions")

        assert recurring_idx < missing_idx < human_idx < suggestions_idx

    def test_calls_attribute_renderer_for_each_section(
        self, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()

        with patch(
            "compliance.services.site_analysis._render_site_analysis_attribute",
            return_value="\nRendered section",
        ) as mock_render_attr:
            result = render_site_analysis_markdown(site_analysis)

        assert mock_render_attr.call_count == 4
        mock_render_attr.assert_any_call(site_analysis, "recurring_issues")
        mock_render_attr.assert_any_call(site_analysis, "missing_information")
        mock_render_attr.assert_any_call(site_analysis, "needs_human_review")
        mock_render_attr.assert_any_call(site_analysis, "suggestions")
        assert result.count("Rendered section") == 4


class TestBeautifyAttrName:
    def test_replaces_underscores_with_spaces(self) -> None:
        assert _beautify_attr_name("needs_human_review") == "Needs human review"

    def test_capitalizes_single_word_attributes(self) -> None:
        assert _beautify_attr_name("suggestions") == "Suggestions"

    def test_returns_empty_string_when_input_is_empty(self) -> None:
        assert _beautify_attr_name("") == ""

    def test_converts_only_underscores_to_spaces(self) -> None:
        assert _beautify_attr_name("___") == "   "

    def test_preserves_whitespace_only_strings(self) -> None:
        assert _beautify_attr_name("   ") == "   "

    def test_replaces_leading_and_trailing_underscores_with_spaces(self) -> None:
        assert _beautify_attr_name("_basis_") == " basis "


class TestRenderSiteAnalysisAttribute:
    def test_returns_none_when_attr_name_is_empty(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = _render_site_analysis_attribute(site_analysis, "")

        assert result == "\nNone."

    def test_returns_none_when_attribute_is_empty_list(
        self, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory(suggestions=[])

        result = _render_site_analysis_attribute(site_analysis, "suggestions")

        assert result == "\nNone."

    def test_renders_item_attributes_and_single_evidence(
        self, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()

        result = _render_site_analysis_attribute(site_analysis, "suggestions")

        assert "### Check labeling records" in result
        assert "#### Basis" in result
        assert "Prior labeling issue suggests targeted follow-up." in result
        assert "#### Evidence" in result
        assert "Suggestion evidence." in result

    def test_renders_multiple_evidence_items(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = _render_site_analysis_attribute(site_analysis, "recurring_issues")

        assert result.count("#### Evidence") == 2
        assert "Recurring evidence 1." in result
        assert "Recurring evidence 2." in result


class TestFormatEvidenceItemToMarkdown:
    def test_renders_all_available_fields(self, evidence_ref_factory) -> None:
        evidence = evidence_ref_factory()

        result = _format_evidence_item_to_markdown(evidence)

        assert result == (
            "\n#### Evidence\n"
            "- Certification ID: 100\n"
            "- Regulation title: USDA Organic\n"
            "- Inspection date: 2024-01-10\n"
            "- Finding ID: 1\n"
            "- Rule index: 7 CFR 205.201\n"
            "- Description: Inspector noted labeling issue."
        )

    def test_uses_empty_header_level_without_raising(
        self, evidence_ref_factory
    ) -> None:
        evidence = evidence_ref_factory()

        result = _format_evidence_item_to_markdown(evidence, header_level="")

        assert result.startswith("\n Evidence\n")
        assert "- Certification ID: 100" in result
        assert "- Regulation title: USDA Organic" in result

    def test_uses_custom_header_level(self, evidence_ref_factory) -> None:
        evidence = evidence_ref_factory()

        result = _format_evidence_item_to_markdown(evidence, header_level="##")

        assert result.startswith("\n## Evidence\n")
        assert "- Certification ID: 100" in result

    def test_omits_none_optional_fields(self, evidence_ref_factory) -> None:
        evidence = evidence_ref_factory(
            finding_id=None,
            rule_index=None,
            inspection_date=None,
        )

        result = _format_evidence_item_to_markdown(evidence)

        assert "- Certification ID: 100" in result
        assert "- Regulation title: USDA Organic" in result
        assert "- Inspection date:" not in result
        assert "- Finding ID:" not in result
        assert "- Rule index:" not in result
        assert "- Description: Inspector noted labeling issue." in result

    def test_renders_empty_support_text_and_regulation_title(
        self, evidence_ref_factory
    ) -> None:
        evidence = evidence_ref_factory(
            reg_title="",
            rule_index="",
            inspection_date=None,
            finding_id=None,
            support_text="",
        )

        result = _format_evidence_item_to_markdown(evidence)

        assert "- Regulation title: " in result
        assert "- Description: " in result
        assert "- Inspection date:" not in result
        assert "- Finding ID:" not in result
        assert "- Rule index:" not in result
