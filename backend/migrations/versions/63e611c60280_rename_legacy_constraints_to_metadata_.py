"""rename legacy constraints to metadata naming convention

Revision ID: 63e611c60280
Revises: 561e6f89ce9e
Create Date: 2026-05-15 14:07:18.595960

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63e611c60280"
down_revision: str | Sequence[str] | None = "561e6f89ce9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_constraint(table_name: str, old_name: str, new_name: str) -> None:
    op.execute(
        f'ALTER TABLE "{table_name}" ' f'RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
    )


def upgrade() -> None:
    """Rename legacy constraints to match SQLAlchemy metadata names."""
    _rename_constraint("clients", "clients_pkey", "pk_clients")
    _rename_constraint("clients", "uq_company_name", "uq_clients_company_name")

    _rename_constraint("certifiers", "certifiers_pkey", "pk_certifiers")
    _rename_constraint(
        "certifiers", "uq_organization_name", "uq_certifiers_organization_name"
    )

    _rename_constraint("regulations", "regulations_pkey", "pk_regulations")
    _rename_constraint("regulations", "uq_title", "uq_regulations_title")

    _rename_constraint("rules", "rules_pkey", "pk_rules")
    _rename_constraint(
        "rules", "uq_regulation_id_rule_index", "uq_rules_regulation_id_rule_index"
    )
    _rename_constraint(
        "rules", "rules_regulation_id_fkey", "fk_rules_regulation_id_regulations"
    )

    _rename_constraint("sites", "sites_pkey", "pk_sites")
    _rename_constraint("sites", "sites_nif_fkey", "fk_sites_nif_clients")

    _rename_constraint("certifications", "certifications_pkey", "pk_certifications")
    _rename_constraint(
        "certifications",
        "certifications_certifier_id_fkey",
        "fk_certifications_certifier_id_certifiers",
    )
    _rename_constraint(
        "certifications",
        "certifications_regulation_id_fkey",
        "fk_certifications_regulation_id_regulations",
    )
    _rename_constraint(
        "certifications",
        "certifications_site_id_fkey",
        "fk_certifications_site_id_sites",
    )
    _rename_constraint(
        "certifications", "result_check", "ck_certifications_result_check"
    )

    _rename_constraint("attachments", "attachments_pkey", "pk_attachments")
    _rename_constraint(
        "attachments",
        "uq_attachment_id_certification_id",
        "uq_attachments_id_certification_id",
    )
    _rename_constraint(
        "attachments",
        "attachments_certification_id_fkey",
        "fk_attachments_certification_id_certifications",
    )

    _rename_constraint("findings", "findings_pkey", "pk_findings")
    _rename_constraint(
        "findings",
        "uq_finding_id_certification_id",
        "uq_findings_id_certification_id",
    )
    _rename_constraint(
        "findings",
        "findings_certification_id_fkey",
        "fk_findings_certification_id_certifications",
    )
    _rename_constraint("findings", "findings_rule_id_fkey", "fk_findings_rule_id_rules")

    _rename_constraint(
        "finding_attachments",
        "finding_attachments_pkey",
        "pk_finding_attachments",
    )
    _rename_constraint(
        "finding_attachments",
        "fk_finding_id_certification_id",
        "fk_finding_attachments_finding_id_id_certification_id_certification_id",
    )
    _rename_constraint(
        "finding_attachments",
        "fk_attachment_id_certification_id",
        "fk_finding_attachments_attachment_id_id_certification_id_certification_id",
    )


def downgrade() -> None:
    """Restore legacy constraint names."""
    _rename_constraint("clients", "pk_clients", "clients_pkey")
    _rename_constraint("clients", "uq_clients_company_name", "uq_company_name")

    _rename_constraint("certifiers", "pk_certifiers", "certifiers_pkey")
    _rename_constraint(
        "certifiers", "uq_certifiers_organization_name", "uq_organization_name"
    )

    _rename_constraint("regulations", "pk_regulations", "regulations_pkey")
    _rename_constraint("regulations", "uq_regulations_title", "uq_title")

    _rename_constraint("rules", "pk_rules", "rules_pkey")
    _rename_constraint(
        "rules", "uq_rules_regulation_id_rule_index", "uq_regulation_id_rule_index"
    )
    _rename_constraint(
        "rules", "fk_rules_regulation_id_regulations", "rules_regulation_id_fkey"
    )

    _rename_constraint("sites", "pk_sites", "sites_pkey")
    _rename_constraint("sites", "fk_sites_nif_clients", "sites_nif_fkey")

    _rename_constraint("certifications", "pk_certifications", "certifications_pkey")
    _rename_constraint(
        "certifications",
        "fk_certifications_certifier_id_certifiers",
        "certifications_certifier_id_fkey",
    )
    _rename_constraint(
        "certifications",
        "fk_certifications_regulation_id_regulations",
        "certifications_regulation_id_fkey",
    )
    _rename_constraint(
        "certifications",
        "fk_certifications_site_id_sites",
        "certifications_site_id_fkey",
    )
    _rename_constraint(
        "certifications", "ck_certifications_result_check", "result_check"
    )

    _rename_constraint("attachments", "pk_attachments", "attachments_pkey")
    _rename_constraint(
        "attachments",
        "uq_attachments_id_certification_id",
        "uq_attachment_id_certification_id",
    )
    _rename_constraint(
        "attachments",
        "fk_attachments_certification_id_certifications",
        "attachments_certification_id_fkey",
    )

    _rename_constraint("findings", "pk_findings", "findings_pkey")
    _rename_constraint(
        "findings",
        "uq_findings_id_certification_id",
        "uq_finding_id_certification_id",
    )
    _rename_constraint(
        "findings",
        "fk_findings_certification_id_certifications",
        "findings_certification_id_fkey",
    )
    _rename_constraint("findings", "fk_findings_rule_id_rules", "findings_rule_id_fkey")

    _rename_constraint(
        "finding_attachments",
        "pk_finding_attachments",
        "finding_attachments_pkey",
    )
    _rename_constraint(
        "finding_attachments",
        "fk_finding_attachments_finding_id_id_certification_id_certification_id",
        "fk_finding_id_certification_id",
    )
    _rename_constraint(
        "finding_attachments",
        "fk_finding_attachments_attachment_id_id_certification_id_certification_id",
        "fk_attachment_id_certification_id",
    )
