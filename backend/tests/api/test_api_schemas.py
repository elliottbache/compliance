from compliance.api import schemas as api_schemas
from compliance.services import schemas as service_schemas


class TestApiSchemas:
    def test_api_schemas_are_service_schema_aliases(self) -> None:
        assert api_schemas.ArchiveRequest is service_schemas.ArchiveRequest
        assert api_schemas.AttachmentCreate is service_schemas.AttachmentCreate
        assert api_schemas.AttachmentOut is service_schemas.AttachmentOut
        assert (
            api_schemas.AttachmentWithContextOut
            is service_schemas.AttachmentWithContextOut
        )
        assert api_schemas.AuditEventOut is service_schemas.AuditEventOut
        assert (
            api_schemas.CertificationAttachmentsOut
            is service_schemas.CertificationAttachmentsOut
        )
        assert api_schemas.CertificationCreate is service_schemas.CertificationCreate
        assert api_schemas.CertificationOut is service_schemas.CertificationOut
        assert api_schemas.CertifierCreate is service_schemas.CertifierCreate
        assert api_schemas.CertifierOut is service_schemas.CertifierOut
        assert api_schemas.ClientCreate is service_schemas.ClientCreate
        assert api_schemas.ClientOut is service_schemas.ClientOut
        assert api_schemas.FindingAttachmentOut is service_schemas.FindingAttachmentOut
        assert api_schemas.FindingCreate is service_schemas.FindingCreate
        assert api_schemas.FindingOut is service_schemas.FindingOut
        assert api_schemas.RegulationCreate is service_schemas.RegulationCreate
        assert api_schemas.RegulationOut is service_schemas.RegulationOut
        assert api_schemas.RuleCreate is service_schemas.RuleCreate
        assert api_schemas.RuleOut is service_schemas.RuleOut
        assert api_schemas.SiteAttachmentsOut is service_schemas.SiteAttachmentsOut
        assert (
            api_schemas.SiteCertificationsOut is service_schemas.SiteCertificationsOut
        )
        assert api_schemas.SiteCreate is service_schemas.SiteCreate
        assert api_schemas.SiteOut is service_schemas.SiteOut
        assert api_schemas.UserCreate is service_schemas.UserCreate
        assert api_schemas.UserOut is service_schemas.UserOut

    def test_api_create_schema_remains_service_compatible(self) -> None:
        client = api_schemas.ClientCreate(
            nif="A1234567B",
            company_name="Example Farm",
            contact_name="Alice Inspector",
            email="alice@example.com",
            telephone=555123456,
        )

        assert isinstance(client, service_schemas.ClientCreate)
        assert service_schemas.ClientCreate.model_validate(client) == client

    def test_api_output_schema_accepts_service_output_instance(self) -> None:
        finding = service_schemas.FindingOut(
            finding_id=18,
            finding="Missing document",
            site_id=12,
            certification_id=100,
            certification_title="USDA Organic",
            certification_resolution_date=None,
            rule_id=5,
            rule_index="7 CFR 205.201",
            rule_title="Organic plan",
            rule_description="Producer must maintain an organic system plan.",
            attachments=[],
            archived_at=None,
            archive_reason=None,
        )

        assert api_schemas.FindingOut.model_validate(finding) == finding
