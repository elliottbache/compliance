from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Finding(BaseModel):
    """Represents a single inspection finding tied to a regulation rule."""

    model_config = ConfigDict(frozen=True)

    finding_id: int
    finding: str
    rule_index: str
    rule_title: str | None
    rule_description: str


class Certification(BaseModel):
    """Represents one certification record and its associated findings."""

    model_config = ConfigDict(frozen=True)

    cert_id: int
    result: str | None
    resolution_date: date | None
    reg_title: str
    reg_description: str
    certifier_org_name: str
    inspection_date: date | None
    findings: list[Finding] = Field(default_factory=list)


class Site(BaseModel):
    """Represents a site's certification history and inspection summary."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    certifications: list[Certification] = Field(default_factory=list)
    inspection_count: int = Field(default=0)
    latest_inspection_date: date | None
