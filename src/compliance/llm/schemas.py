from datetime import date

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    """The evidence for a model claim."""

    cert_id: int
    reg_title: str
    finding_id: int | None
    rule_index: str | None
    inspection_date: date | None
    support_text: str


class RecurringIssueItem(BaseModel):
    """A recurring issue."""

    item: str
    evidence: list[EvidenceRef] = Field(min_length=2)
    confidence_note: str


class MissingInfoItem(BaseModel):
    """A missing item"""

    item: str
    why_missing_matters: str
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=1)


class HumanReviewItem(BaseModel):
    """A human review item"""

    item: str
    evidence: list[EvidenceRef] = Field(min_length=1)


class SuggestionItem(BaseModel):
    """A suggestion item"""

    item: str
    basis: str
    evidence: list[EvidenceRef] = Field(min_length=1)


class SiteAnalysis(BaseModel):
    """Returned from the model."""

    site_id: int
    inspection_count: int
    executive_summary: str
    recurring_issues: list[RecurringIssueItem]
    missing_information: list[MissingInfoItem]
    needs_human_review: list[HumanReviewItem]
    suggestions: list[SuggestionItem]


class UserBrief(BaseModel):
    headline_summary: str
    top_recurring_issues: list[str]
    open_questions: list[str]
    visit_preparation_points: list[str]


class ExpectedResults(BaseModel):
    """Expected eval metrics from file."""

    site_id: int
    inspection_count: int
    max_summary_sentences: int
    summary_phrases: list[str] = Field(default_factory=list)
    recurring_issues: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    needs_human_review: list[str] = Field(default_factory=list)
    rule_mentions: list[str] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)
    forbidden_summary_terms: list[str] = Field(default_factory=list)


class ResultChecks(BaseModel):
    """Eval metrics."""

    is_site_id_correct: bool
    is_n_inspections_correct: bool
    is_max_summary_sentences: bool
    is_summary_phrases: bool = True
    is_recurring_issues: bool = True
    is_missing_information: bool = True
    is_needs_human_review: bool = True
    is_rule_mentions: bool = True
    is_evidence_references: bool = True
    is_valid_references: bool = True
    is_forbidden_phrases: bool = False
    is_forbidden_summary_terms: bool = False
