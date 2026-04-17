from datetime import date

from pydantic import BaseModel, Field, ConfigDict


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
    model_config = ConfigDict(frozen=True)

    site_id: int
    certifications: list[Certification] = Field(default_factory=list)
    inspection_count: int = Field(default=0)
    latest_inspection_date: date | None
