from unittest.mock import patch

from compliance.services.reports import (
    _beautify_attr_name,
    _format_evidence_item_to_markdown,
    _render_site_analysis_attribute,
    build_site_analysis_markdown,
)


class TestBuildSiteAnalysisMarkdown:
    def test_renders_full_markdown_document(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = build_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Note\nEverything in this report is AI-generated and is meant for human-review-only.  These are not official compliance decisions.\n## Executive summary\nShort summary."
        )
        assert "## Recurring issues" in result
        assert "## Missing information" in result
        assert "## Needs human review" in result
        assert "## Suggestions" in result

    def test_renders_empty_executive_summary(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory(executive_summary="")

        result = build_site_analysis_markdown(site_analysis)

        assert result.startswith(
            "# Site Analysis\n## Note\nEverything in this report is AI-generated and is meant for human-review-only.  These are not official compliance decisions.\n## Executive summary\nNone.\n## Recurring issues"
        )

    def test_renders_sections_in_expected_order(self, site_analysis_factory) -> None:
        site_analysis = site_analysis_factory()

        result = build_site_analysis_markdown(site_analysis)

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
            "compliance.services.reports._render_site_analysis_attribute",
            return_value="\nRendered section",
        ) as mock_render_attr:
            result = build_site_analysis_markdown(site_analysis)

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
