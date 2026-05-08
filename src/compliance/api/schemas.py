from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from compliance.schemas import FindingHistory

CertificationResult = Literal["Pass", "Fail"]


class SiteCreate(BaseModel):
    """Public API input shape for creating a site record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    nif: str = Field(min_length=9, max_length=9)
    city: str
    postal_code: int
    street: str
    street_number: int | None = None
    suite: str | None = None
    address_info: str | None = None


class SiteOut(SiteCreate):
    """Public API response shape for a site record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: datetime | None
    archive_reason: str | None


class CertificationCreate(BaseModel):
    """Public API input shape for creating a certification record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    certifier_id: int
    regulation_id: int
    site_id: int
    result: CertificationResult | None = None
    inspection_date: date | None = None
    resolution_date: date | None = None


class CertificationOut(CertificationCreate):
    """Public API response shape for a certification record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: datetime | None
    archive_reason: str | None


class RegulationCreate(BaseModel):
    """Public API input shape for creating a regulation record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    title: str = Field(min_length=1, max_length=80)
    description: str
    published_date: date


class RegulationOut(RegulationCreate):
    """Public API response shape for a regulation record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: datetime | None
    archive_reason: str | None


class RuleCreate(BaseModel):
    """Public API input shape for creating a rule record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    regulation_id: int
    rule_index: str = Field(min_length=1, max_length=10)
    title: str | None = Field(default=None, max_length=80)
    description: str


class RuleOut(RuleCreate):
    """Public API response shape for a rule record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: datetime | None
    archive_reason: str | None


class AttachmentWithContextOut(BaseModel):
    """Public API response shape for an attachment record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    file_type: str
    file_path: str
    description: str | None
    uploaded_at: datetime
    archived_at: datetime | None
    archive_reason: str | None

    certification_id: int
    inspection_date: date | None
    regulation_id: int
    regulation_title: str

    finding_links: list[FindingHistory] = Field(default_factory=list)


class AttachmentCreate(BaseModel):
    """Public API input shape for an attachment metadata record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    file_type: str
    file_name: str
    certification_id: int
    description: str | None = None
    finding_ids: list[int] = Field(default_factory=list)


class AttachmentOut(AttachmentCreate):
    """Public API response shape for an attachment record as in database."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    uploaded_at: datetime
    inspection_date: date | None
    regulation_id: int
    regulation_title: str
    archived_at: datetime | None
    archive_reason: str | None


class SiteAttachmentsOut(BaseModel):
    """Public API response shape for a site's attachments record."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    attachments: list[AttachmentWithContextOut]


class SiteCertificationsOut(BaseModel):
    """Public API response shape for a site's certification records."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    certifications: list[CertificationOut]


class CertificationAttachmentsOut(BaseModel):
    """Public API response shape for a certification's attachments record."""

    model_config = ConfigDict(frozen=True)

    certification_id: int
    attachments: list[AttachmentWithContextOut]


class ClientCreate(BaseModel):
    """Public API input shape for a new client record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    nif: str = Field(min_length=9, max_length=9)
    company_name: str | None
    contact_name: str
    email: str | None
    telephone: int | None


class ClientOut(ClientCreate):
    """Public API response shape for a client record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)
    archived_at: datetime | None
    archive_reason: str | None


class CertifierCreate(BaseModel):
    """Public API input shape for a new certifier record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    organization_name: str = Field(min_length=1, max_length=80)


class CertifierOut(CertifierCreate):
    """Public API response shape for a certifier record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: datetime | None
    archive_reason: str | None


class FindingCreate(BaseModel):
    """Public API input shape for a finding metadata record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    certification_id: int
    rule_id: int
    finding: str
    attachment_ids: list[int] | None = None


class FindingAttachmentOut(BaseModel):
    """Public API output shape for an attachment linked to a finding."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    attachment_id: int
    file_type: str
    file_path: str
    description: str | None
    uploaded_at: datetime
    archived_at: datetime | None
    archive_reason: str | None


class FindingOut(BaseModel):
    """Public API output shape for a finding record."""

    model_config = ConfigDict(frozen=True)

    finding_id: int
    finding: str
    site_id: int
    certification_id: int
    certification_title: str
    certification_resolution_date: date | None
    rule_id: int
    rule_index: str
    rule_title: str | None
    rule_description: str
    attachments: list[FindingAttachmentOut] = Field(default_factory=list)
    archived_at: datetime | None
    archive_reason: str | None


class ArchiveRequest(BaseModel):
    archive_reason: str | None = Field(max_length=160, default=None)
