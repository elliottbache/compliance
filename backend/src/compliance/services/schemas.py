"""Service-layer schemas shared by business logic and API adapters."""

from datetime import date
from typing import Literal

from compliance.db.models import Role
from compliance.schemas import FindingHistory
from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field

CertificationResult = Literal["Pass", "Fail"]


class UserCreate(BaseModel):
    """Input shape for creating a user."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    full_name: str = Field(min_length=1, max_length=80)
    email: EmailStr


class UserOut(UserCreate):
    """Output shape for a user."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    role: Role = Role.VIEWER
    is_active: bool = True
    created_at: AwareDatetime


class UserInDB(UserOut):
    hashed_password: str


class SiteCreate(BaseModel):
    """Input shape for creating a site record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    nif: str = Field(min_length=9, max_length=9)
    city: str
    postal_code: int
    street: str
    street_number: int | None = None
    suite: str | None = None
    address_info: str | None = None


class SiteOut(SiteCreate):
    """Output shape for a site record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: AwareDatetime | None
    archive_reason: str | None


class CertificationCreate(BaseModel):
    """Input shape for creating a certification record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    certifier_id: int
    regulation_id: int
    site_id: int
    inspector_id: int | None = None
    result: CertificationResult | None = None
    inspection_date: date | None = None
    resolution_date: date | None = None


class CertificationOut(CertificationCreate):
    """Output shape for a certification record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: AwareDatetime | None
    archive_reason: str | None


class RegulationCreate(BaseModel):
    """Input shape for creating a regulation record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    title: str = Field(min_length=1, max_length=80)
    description: str
    published_date: date


class RegulationOut(RegulationCreate):
    """Output shape for a regulation record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: AwareDatetime | None
    archive_reason: str | None


class RuleCreate(BaseModel):
    """Input shape for creating a rule record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    regulation_id: int
    rule_index: str = Field(min_length=1, max_length=10)
    title: str | None = Field(default=None, max_length=80)
    description: str


class RuleOut(RuleCreate):
    """Output shape for a rule record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: AwareDatetime | None
    archive_reason: str | None


class AttachmentWithContextOut(BaseModel):
    """Output shape for an attachment with certification and finding context."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    file_name: str | None
    file_path: str | None
    description: str | None
    uploaded_at: AwareDatetime | None
    archived_at: AwareDatetime | None
    archive_reason: str | None

    certification_id: int
    inspection_date: date | None
    regulation_id: int
    regulation_title: str

    finding_links: list[FindingHistory] = Field(default_factory=list)


class AttachmentCreate(BaseModel):
    """Input shape for creating attachment metadata."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    file_name: str | None = None
    certification_id: int
    description: str | None = None
    finding_ids: list[int] = Field(default_factory=list)


class AttachmentOut(AttachmentCreate):
    """Output shape for attachment metadata."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    file_path: str | None
    uploaded_at: AwareDatetime | None
    inspection_date: date | None
    regulation_id: int
    regulation_title: str
    archived_at: AwareDatetime | None
    archive_reason: str | None


class SiteAttachmentsOut(BaseModel):
    """Output shape for a site's attachment collection."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    attachments: list[AttachmentWithContextOut]


class SiteCertificationsOut(BaseModel):
    """Output shape for a site's certification collection."""

    model_config = ConfigDict(frozen=True)

    site_id: int
    certifications: list[CertificationOut]


class CertificationAttachmentsOut(BaseModel):
    """Output shape for a certification's attachment collection."""

    model_config = ConfigDict(frozen=True)

    certification_id: int
    attachments: list[AttachmentWithContextOut]


class ClientCreate(BaseModel):
    """Input shape for creating a client record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    nif: str = Field(min_length=9, max_length=9)
    company_name: str | None
    contact_name: str
    email: str | None
    telephone: int | None


class ClientOut(ClientCreate):
    """Output shape for a client record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)
    archived_at: AwareDatetime | None
    archive_reason: str | None


class CertifierCreate(BaseModel):
    """Input shape for creating a certifier record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    organization_name: str = Field(min_length=1, max_length=80)


class CertifierOut(CertifierCreate):
    """Output shape for a certifier record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    id: int
    archived_at: AwareDatetime | None
    archive_reason: str | None


class FindingCreate(BaseModel):
    """Input shape for creating a finding record."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    certification_id: int
    rule_id: int
    finding: str
    attachment_ids: list[int] | None = None


class FindingAttachmentOut(BaseModel):
    """Output shape for an attachment linked to a finding."""

    model_config = ConfigDict(frozen=True, from_attributes=True)

    attachment_id: int
    file_name: str | None
    file_path: str | None
    description: str | None
    uploaded_at: AwareDatetime | None
    archived_at: AwareDatetime | None
    archive_reason: str | None


class FindingOut(BaseModel):
    """Output shape for a finding record."""

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
    archived_at: AwareDatetime | None
    archive_reason: str | None


class ArchiveRequest(BaseModel):
    """Input shape for archive metadata."""

    archive_reason: str | None = Field(max_length=160, default=None)
