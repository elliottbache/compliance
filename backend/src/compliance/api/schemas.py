"""HTTP request and response schemas exposed by the FastAPI layer."""

from compliance.services import schemas as service_schemas

CertificationResult = service_schemas.CertificationResult


class UserCreate(service_schemas.UserCreate):
    """HTTP request body for creating a user."""


class UserOut(service_schemas.UserOut):
    """HTTP response body for a user."""


class SiteCreate(service_schemas.SiteCreate):
    """HTTP request body for creating a site."""


class SiteOut(service_schemas.SiteOut):
    """HTTP response body for a site."""


class CertificationCreate(service_schemas.CertificationCreate):
    """HTTP request body for creating a certification."""


class CertificationOut(service_schemas.CertificationOut):
    """HTTP response body for a certification."""


class RegulationCreate(service_schemas.RegulationCreate):
    """HTTP request body for creating a regulation."""


class RegulationOut(service_schemas.RegulationOut):
    """HTTP response body for a regulation."""


class RuleCreate(service_schemas.RuleCreate):
    """HTTP request body for creating a rule."""


class RuleOut(service_schemas.RuleOut):
    """HTTP response body for a rule."""


class AttachmentWithContextOut(service_schemas.AttachmentWithContextOut):
    """HTTP response body for an attachment with certification and finding context."""


class AttachmentCreate(service_schemas.AttachmentCreate):
    """HTTP request body for creating attachment metadata."""


class AttachmentOut(service_schemas.AttachmentOut):
    """HTTP response body for attachment metadata."""


class SiteAttachmentsOut(service_schemas.SiteAttachmentsOut):
    """HTTP response body for a site's attachment collection."""


class SiteCertificationsOut(service_schemas.SiteCertificationsOut):
    """HTTP response body for a site's certification collection."""


class CertificationAttachmentsOut(service_schemas.CertificationAttachmentsOut):
    """HTTP response body for a certification's attachment collection."""


class ClientCreate(service_schemas.ClientCreate):
    """HTTP request body for creating a client."""


class ClientOut(service_schemas.ClientOut):
    """HTTP response body for a client."""


class CertifierCreate(service_schemas.CertifierCreate):
    """HTTP request body for creating a certifier."""


class CertifierOut(service_schemas.CertifierOut):
    """HTTP response body for a certifier."""


class FindingCreate(service_schemas.FindingCreate):
    """HTTP request body for creating a finding."""


class FindingAttachmentOut(service_schemas.FindingAttachmentOut):
    """HTTP response body for an attachment linked to a finding."""


class FindingOut(service_schemas.FindingOut):
    """HTTP response body for a finding."""


class ArchiveRequest(service_schemas.ArchiveRequest):
    """HTTP request body for archive metadata."""


__all__ = [
    "ArchiveRequest",
    "AttachmentCreate",
    "AttachmentOut",
    "AttachmentWithContextOut",
    "CertificationAttachmentsOut",
    "CertificationCreate",
    "CertificationOut",
    "CertificationResult",
    "CertifierCreate",
    "CertifierOut",
    "ClientCreate",
    "ClientOut",
    "FindingAttachmentOut",
    "FindingCreate",
    "FindingOut",
    "RegulationCreate",
    "RegulationOut",
    "RuleCreate",
    "RuleOut",
    "SiteAttachmentsOut",
    "SiteCertificationsOut",
    "SiteCreate",
    "SiteOut",
    "UserCreate",
    "UserOut",
]
