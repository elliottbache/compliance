from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRef(BaseModel):
    """Represents a citation from site history supporting an LLM claim."""
    model_config = ConfigDict(frozen=True)

    cert_id: int
    reg_title: str
    finding_id: int | None
    rule_index: str | None
    inspection_date: date | None
    support_text: str


class RecurringIssueItem(BaseModel):
    """Represents a recurring issue identified across inspections."""
    model_config = ConfigDict(frozen=True)

    item: str
    confidence_note: str
    evidence: list[EvidenceRef] = Field(min_length=2)


class MissingInfoItem(BaseModel):
    """Represents information the model could not confirm from the record."""
    model_config = ConfigDict(frozen=True)

    item: str
    why_missing_matters: str
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=1)


class HumanReviewItem(BaseModel):
    """Represents an issue that should be escalated for human review."""
    model_config = ConfigDict(frozen=True)

    item: str
    evidence: list[EvidenceRef] = Field(min_length=1)


class SuggestionItem(BaseModel):
    """Represents a suggested next step grounded in historical evidence."""
    model_config = ConfigDict(frozen=True)

    item: str
    basis: str
    evidence: list[EvidenceRef] = Field(min_length=1)


class SiteAnalysis(BaseModel):
    """Represents the structured LLM analysis returned for a site."""
    model_config = ConfigDict(frozen=True)

    site_id: int
    inspection_count: int
    executive_summary: str
    recurring_issues: list[RecurringIssueItem]
    missing_information: list[MissingInfoItem]
    needs_human_review: list[HumanReviewItem]
    suggestions: list[SuggestionItem]


class ExpectedResults(BaseModel):
    """Represents expected evaluation outcomes loaded from a test fixture."""
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
    """Represents pass/fail checks for a site analysis evaluation."""
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
