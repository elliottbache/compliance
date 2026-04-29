from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from compliance.schemas import FindingHistory


class SiteOutput(BaseModel):
    """Public API response shape for a site record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    nif: str = Field(min_length=9, max_length=9)
    city: str
    postal_code: int
    street: str
    street_number: int | None
    suite: str | None
    address_info: str | None


class CertificationOutput(BaseModel):
    """Public API response shape for a certification record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    certifier_id: int
    regulation_id: int
    site_id: int
    result: str | None
    inspection_date: date | None
    resolution_date: date | None


class AttachmentWithContextOutput(BaseModel):
    """Public API response shape for an attachment record."""

    model_config = ConfigDict(frozen=True)

    id: int
    file_type: str
    file_path: str
    description: str | None
    uploaded_at: date

    certification_id: int
    inspection_date: date | None
    regulation_id: int
    regulation_title: str

    finding_links: list[FindingHistory] = Field(default_factory=list)


class SiteAttachments(BaseModel):
    """Public API response shape for a site's attachments record."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    attachments: list[AttachmentWithContextOutput]
