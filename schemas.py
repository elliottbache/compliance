from datetime import date
from pydantic import BaseModel, Field

class SiteAnalysis(BaseModel):
    site_id: int
    inspection_count: int
    summary: str
    recurring_issues: list[str]
    missing_information: list[str]
    needs_human_review: list[str]
    inspection_caveats: list[str]
    suggestions: list[str]


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
    organization_name: str
    inspection_date: date | None
    findings: list[Finding] = Field(default_factory=list)


class Site(BaseModel):
    site_id: int
    certifications: list[Certification] = Field(default_factory=list)
    n_inspections: int = Field(default=0)
    latest_inspection_date: date | None

