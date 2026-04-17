from datetime import date
from unittest.mock import call, patch

import pytest

from compliance._helpers import _validate_evidence_ref, validate_llm_references
from compliance.llm.schemas import (
    EvidenceRef,
    MissingInfoItem,
    RecurringIssueItem,
    SiteAnalysis,
    SuggestionItem,
)
from compliance.schemas import Certification, Finding, Site


@pytest.fixture
def site_history() -> Site:
    return Site(
        site_id=71,
        inspection_count=2,
        latest_inspection_date=date(2024, 2, 1),
        certifications=[
            Certification(
                cert_id=100,
                result="pass",
                resolution_date=None,
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
            ),
            Certification(
                cert_id=200,
                result="pass",
                resolution_date=None,
                reg_title="USDA Organic",
                reg_description="Organic certification",
                certifier_org_name="Org B",
                inspection_date=date(2024, 2, 1),
                findings=[
                    Finding(
                        finding_id=99,
                        finding="Issue B",
                        rule_index="7 CFR 205.202",
                        rule_title="Rule B",
                        rule_description="Rule description B",
                    )
                ],
            ),
        ],
    )


class TestValidateLlmReferences:
    def test_skips_when_all_site_attrs_are_empty_lists(
        self, site_history: Site
    ) -> None:
        site_analysis = SiteAnalysis(
            site_id=71,
            inspection_count=2,
            executive_summary="",
            recurring_issues=[],
            missing_information=[],
            needs_human_review=[],
            suggestions=[],
        )

        with patch("compliance._helpers._validate_evidence_ref") as mock_validate:
            validate_llm_references(site_analysis, site_history)

        mock_validate.assert_not_called()

    def test_visits_every_evidence_ref(self, site_history: Site) -> None:
        recurring_evidence_1 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=date(2024, 1, 10),
            support_text="support 1",
        )
        recurring_evidence_2 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="support 2",
        )
        missing_info_evidence = EvidenceRef(
            cert_id=200,
            reg_title="USDA Organic",
            finding_id=99,
            rule_index="7 CFR 205.202",
            inspection_date=date(2024, 2, 1),
            support_text="support 3",
        )

        site_analysis = SiteAnalysis(
            site_id=71,
            inspection_count=2,
            executive_summary="",
            recurring_issues=[
                RecurringIssueItem(
                    item="issue",
                    confidence_note="high confidence",
                    evidence=[recurring_evidence_1, recurring_evidence_2],
                )
            ],
            missing_information=[
                MissingInfoItem(
                    item="missing doc",
                    why_missing_matters="needed for review",
                    evidence=[missing_info_evidence],
                )
            ],
            needs_human_review=[],
            suggestions=[],
        )

        with patch("compliance._helpers._validate_evidence_ref") as mock_validate:
            validate_llm_references(site_analysis, site_history)

        assert mock_validate.call_count == 3
        mock_validate.assert_has_calls(
            [
                call(recurring_evidence_1, site_history),
                call(recurring_evidence_2, site_history),
                call(missing_info_evidence, site_history),
            ]
        )

    def test_propagates_value_error_from_nested_evidence_validation(
        self, site_history: Site
    ) -> None:
        evidence_1 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=date(2024, 1, 10),
            support_text="support 1",
        )
        evidence_2 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="support 2",
        )

        site_analysis = SiteAnalysis(
            site_id=71,
            inspection_count=2,
            executive_summary="",
            recurring_issues=[
                RecurringIssueItem(
                    item="issue",
                    confidence_note="high confidence",
                    evidence=[evidence_1, evidence_2],
                )
            ],
            missing_information=[],
            needs_human_review=[],
            suggestions=[],
        )

        with (
            patch(
                "compliance._helpers._validate_evidence_ref",
                side_effect=ValueError("bad evidence"),
            ),
            pytest.raises(ValueError, match="bad evidence"),
        ):
            validate_llm_references(site_analysis, site_history)

    def test_skips_empty_sections_and_visits_populated_sections(
        self, site_history: Site
    ) -> None:
        recurring_evidence_1 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=date(2024, 1, 10),
            support_text="support 1",
        )
        recurring_evidence_2 = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="support 2",
        )
        suggestion_evidence = EvidenceRef(
            cert_id=200,
            reg_title="USDA Organic",
            finding_id=99,
            rule_index="7 CFR 205.202",
            inspection_date=date(2024, 2, 1),
            support_text="support 3",
        )

        site_analysis = SiteAnalysis(
            site_id=71,
            inspection_count=2,
            executive_summary="",
            recurring_issues=[
                RecurringIssueItem(
                    item="issue",
                    confidence_note="high confidence",
                    evidence=[recurring_evidence_1, recurring_evidence_2],
                )
            ],
            missing_information=[],
            needs_human_review=[],
            suggestions=[
                SuggestionItem(
                    item="follow up",
                    basis="based on evidence",
                    evidence=[suggestion_evidence],
                )
            ],
        )

        with patch("compliance._helpers._validate_evidence_ref") as mock_validate:
            validate_llm_references(site_analysis, site_history)

        assert mock_validate.call_count == 3
        mock_validate.assert_has_calls(
            [
                call(recurring_evidence_1, site_history),
                call(recurring_evidence_2, site_history),
                call(suggestion_evidence, site_history),
            ]
        )


class TestValidateEvidenceRef:
    def test_allows_none_finding_id_and_none_rule_index(
        self, site_history: Site
    ) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="some support",
        )

        _validate_evidence_ref(evidence, site_history)

    def test_rejects_empty_rule_index_when_finding_id_is_none(
        self, site_history: Site
    ) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index="",
            inspection_date=None,
            support_text="some support",
        )

        with pytest.raises(ValueError, match="Rule index should not exist"):
            _validate_evidence_ref(evidence, site_history)

    def test_allows_none_inspection_date(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=None,
            support_text="some support",
        )

        _validate_evidence_ref(evidence, site_history)

    def test_allows_empty_support_text(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=date(2024, 1, 10),
            support_text="",
        )

        _validate_evidence_ref(evidence, site_history)

    def test_rejects_finding_from_different_certification(
        self, site_history: Site
    ) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=99,
            rule_index="7 CFR 205.202",
            inspection_date=date(2024, 1, 10),
            support_text="some support",
        )

        with pytest.raises(ValueError, match=r"Finding 99 is not in certification 100"):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_empty_rule_index_when_finding_exists(
        self, site_history: Site
    ) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="",
            inspection_date=date(2024, 1, 10),
            support_text="some support",
        )

        with pytest.raises(ValueError, match="there should be a rule index"):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_unknown_certification(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=999,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="some support",
        )

        with pytest.raises(
            ValueError, match="Certification 999 is not in site history"
        ):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_wrong_regulation_title(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="Different Regulation",
            finding_id=None,
            rule_index=None,
            inspection_date=None,
            support_text="some support",
        )

        with pytest.raises(ValueError, match="Wrong regulation title"):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_wrong_inspection_date(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="7 CFR 205.201",
            inspection_date=date(2024, 1, 11),
            support_text="some support",
        )

        with pytest.raises(ValueError, match="Wrong inspection date"):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_wrong_rule_index_for_existing_finding(
        self, site_history: Site
    ) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=1,
            rule_index="WRONG",
            inspection_date=date(2024, 1, 10),
            support_text="some support",
        )

        with pytest.raises(ValueError, match="Wrong rule index"):
            _validate_evidence_ref(evidence, site_history)

    def test_rejects_rule_index_without_finding_id(self, site_history: Site) -> None:
        evidence = EvidenceRef(
            cert_id=100,
            reg_title="USDA Organic",
            finding_id=None,
            rule_index="7 CFR 205.201",
            inspection_date=None,
            support_text="some support",
        )

        with pytest.raises(ValueError, match="Rule index should not exist"):
            _validate_evidence_ref(evidence, site_history)
