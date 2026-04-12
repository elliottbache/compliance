from datetime import date
from pydantic import BaseModel, Field


class Finding(BaseModel):
    finding_id: int
    finding: str
    rule_index: str
    rule_title: str | None
    rule_description: str


class Certification(BaseModel):
    cert_id: int
    result: str | None
    resolution_date: date | None
    reg_title: str
    reg_description: str
    certifier_org_name: str
    inspection_date: date | None
    findings: list[Finding] = Field(default_factory=list)


class Site(BaseModel):
    site_id: int
    certifications: list[Certification] = Field(default_factory=list)
    inspection_count: int = Field(default=0)
    latest_inspection_date: date | None


class SummaryChecks(BaseModel):
    """Eval metrics."""
    is_site_id_correct: bool
    is_n_inspections_correct: bool
    is_max_summary_sentences: bool
    is_summary_phrases: bool = True
    is_recurring_issues: bool = True
    is_missing_information: bool = True
    is_needs_human_review: bool = True
    is_rule_mentions: bool = True
    is_forbidden_phrases: bool = False
    is_forbidden_summary_terms: bool = False


class SiteAnalysis(BaseModel):
    """Returned from the model."""
    site_id: int
    inspection_count: int
    summary: str
    recurring_issues: list[str]
    missing_information: list[str]
    needs_human_review: list[str]
    inspection_caveats: list[str]
    suggestions: list[str]


class ModelSummary(BaseModel):
    """Expected from model."""
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
