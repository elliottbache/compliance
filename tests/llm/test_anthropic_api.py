import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock
from pydantic import BaseModel, ValidationError

import compliance.llm.anthropic_api as anthropic_api
from compliance.llm.anthropic_api import (
    _beautify_attr_name,
    _call_model,
    _convert_base_model_to_json_schema,
    _convert_response_to_site_analysis,
    _create_error_message,
    _extract_text_from_response,
    _format_evidence_item_to_markdown,
    _log_validation_error_messages,
    _parse_message_to_string,
    _render_site_analysis_attribute,
    _render_site_analysis_markdown,
)
from compliance.llm.schemas import (
    EvidenceRef,
    HumanReviewItem,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import Certification, Finding, Site


@pytest.fixture
def text_block_factory():
    def _build(text: str) -> TextBlock:
        return TextBlock.model_validate({"type": "text", "text": text})

    return _build


@pytest.fixture
def response_factory(text_block_factory):
    def _build(text: str):
        return SimpleNamespace(content=[text_block_factory(text)])

    return _build


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
def site_history() -> Site:
    return Site(
        site_id=71,
        inspection_count=1,
        latest_inspection_date=date(2024, 1, 10),
        certifications=[
            Certification(
                cert_id=100,
                result="pass",
                resolution_date=date(2024, 1, 20),
                reg_title="USDA Organic",
                reg_description="Organic certification",
                certifier_org_name="Org A",
                inspection_date=date(2024, 1, 10),
                findings=[
                    Finding(
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


class ExampleModel(BaseModel):
    value: int


class TestCallModel:
    def test_calls_messages_create_with_expected_payload(self) -> None:
        client = MagicMock()
        schema = {"type": "object"}

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value=schema,
        ):
            _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
            )

        client.messages.create.assert_called_once_with(
            model="claude-test",
            max_tokens=anthropic_api.MAX_TOKENS,
            system="system text",
            messages=[{"role": "user", "content": "user text"}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )

    def test_returns_messages_create_response(self) -> None:
        client = MagicMock()
        response = MagicMock()
        client.messages.create.return_value = response

        with patch(
            "compliance.llm.anthropic_api._convert_base_model_to_json_schema",
            return_value={"type": "object"},
        ):
            result = _call_model(
                client=client,
                ai_model="claude-test",
                system_context="system text",
                user_message="user text",
            )

        assert result == response


class TestConvertBaseModelToJsonSchema:
    def test_transforms_model_json_schema(self) -> None:
        with patch(
            "compliance.llm.anthropic_api.transform_schema",
            return_value={"transformed": True},
        ) as mock_transform:
            result = _convert_base_model_to_json_schema(ExampleModel)

        mock_transform.assert_called_once_with(ExampleModel.model_json_schema())
        assert result == {"transformed": True}


class TestConvertResponseToSiteAnalysis:
    def test_parses_plain_json_response(
        self, response_factory, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()
        response = response_factory(site_analysis.model_dump_json())

        result = _convert_response_to_site_analysis(response)

        assert result == site_analysis

    def test_removes_json_code_fence_before_parsing(
        self, response_factory, site_analysis_factory
    ) -> None:
        site_analysis = site_analysis_factory()
        response = response_factory(f"```json\n{site_analysis.model_dump_json()}\n```")

        result = _convert_response_to_site_analysis(response)

        assert result == site_analysis

    def test_raises_json_decode_error_for_invalid_json(self, response_factory) -> None:
        response = response_factory("not valid json")

        with pytest.raises(json.JSONDecodeError):
            _convert_response_to_site_analysis(response)

    def test_raises_validation_error_for_schema_invalid_json(
        self, response_factory
    ) -> None:
        response = response_factory(json.dumps({"site_id": 71}))

        with pytest.raises(ValidationError):
            _convert_response_to_site_analysis(response)


class TestExtractTextFromResponse:
    def test_returns_text_when_first_content_item_is_text_block(
        self, response_factory
    ) -> None:
        response = response_factory("hello world")

        assert _extract_text_from_response(response) == "hello world"

    def test_raises_when_response_has_no_content(self) -> None:
        response = SimpleNamespace(content=[])

        with pytest.raises(ValueError, match="does not contain text"):
            _extract_text_from_response(response)

    def test_raises_when_first_content_item_is_not_text_block(self) -> None:
        response = SimpleNamespace(content=[{"type": "text", "text": "hello"}])

        with pytest.raises(ValueError, match="does not contain text"):
            _extract_text_from_response(response)


class TestCreateErrorMessage:
    def test_builds_error_message_with_context(self) -> None:
        result = _create_error_message(
            case_info="case-1",
            ai_model="claude-test",
            system_context="system text",
            user_message="user text",
            response="response text",
        )

        assert "case-1" in result
        assert "claude-test" in result
        assert "system text" in result
        assert "user text" in result
        assert "response text" in result
        assert str(anthropic_api.MAX_TOKENS) in result


class TestParseMessageToString:
    def test_returns_text_when_response_contains_text_block(
        self, response_factory
    ) -> None:
        response = response_factory("hello world")

        assert _parse_message_to_string(response) == "hello world"

    def test_returns_empty_string_when_response_has_no_content(self) -> None:
        response = SimpleNamespace(content=[])

        assert _parse_message_to_string(response) == ""

    def test_returns_empty_string_when_first_content_item_is_not_text_block(
        self,
    ) -> None:
        response = SimpleNamespace(content=[{"type": "text", "text": "hello"}])

        assert _parse_message_to_string(response) == ""


class TestLogValidationErrorMessages:
    def test_logs_each_validation_error(self) -> None:
        error = ValidationError.from_exception_data(
            "ExampleModel",
            [
                {"type": "missing", "loc": ("value",), "input": {}},
                {"type": "int_parsing", "loc": ("value",), "input": "abc"},
            ],
        )

        with patch("compliance.llm.anthropic_api.logger.debug") as mock_debug:
            _log_validation_error_messages(error)

        assert mock_debug.call_count == 2

    def test_logs_error_type_location_and_input(self) -> None:
        error = ValidationError.from_exception_data(
            "ExampleModel",
            [{"type": "missing", "loc": ("value",), "input": {}}],
        )

        with patch("compliance.llm.anthropic_api.logger.debug") as mock_debug:
            _log_validation_error_messages(error)

        logged_message = mock_debug.call_args[0][0]
        assert "Error type: missing" in logged_message
        assert "Location:   ('value',)" in logged_message
        assert "Faulty data: {}" in logged_message


class TestRenderSiteAnalysisMarkdown:
    def test_renders_full_markdown_document(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = _render_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Executive summary\nShort summary."
        )
        assert "## Recurring issues" in result
        assert "## Missing information" in result
        assert "## Needs human review" in result
        assert "## Suggestions" in result

    def test_renders_empty_executive_summary(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory(executive_summary="")

        result = _render_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Executive summary\nNone.\n## Recurring issues"
        )

    def test_renders_sections_in_expected_order(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = _render_site_analysis_markdown(site_analysis)

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
            "compliance.llm.anthropic_api._render_site_analysis_attribute",
            return_value="\nRendered section",
        ) as mock_render_attr:
            result = _render_site_analysis_markdown(site_analysis)

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
