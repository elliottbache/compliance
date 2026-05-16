"""Create manually bootstrapped initial schema

Revision ID: 68c51a10a015
Revises: 
Create Date: 2026-05-06 22:20:25.004746

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "68c51a10a015"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the original schema that existed before Alembic migrations."""
    op.create_table(
        "clients",
        sa.Column("nif", sa.String(length=9), nullable=False),
        sa.Column("company_name", sa.String(length=80), nullable=True),
        sa.Column("contact_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=80), nullable=True),
        sa.Column("telephone", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("nif", name="clients_pkey"),
        sa.UniqueConstraint("company_name", name="uq_company_name"),
    )
    op.create_table(
        "certifiers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_name", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id", name="certifiers_pkey"),
        sa.UniqueConstraint("organization_name", name="uq_organization_name"),
    )
    op.create_table(
        "regulations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="regulations_pkey"),
        sa.UniqueConstraint("title", name="uq_title"),
    )
    op.create_table(
        "rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("regulation_id", sa.Integer(), nullable=False),
        sa.Column("rule_index", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["regulation_id"],
            ["regulations.id"],
            name="rules_regulation_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="rules_pkey"),
        sa.UniqueConstraint(
            "regulation_id", "rule_index", name="uq_regulation_id_rule_index"
        ),
    )
    op.create_table(
        "sites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nif", sa.String(length=9), nullable=False),
        sa.Column("city", sa.String(length=40), nullable=False),
        sa.Column("postal_code", sa.Integer(), nullable=False),
        sa.Column("street", sa.String(length=40), nullable=False),
        sa.Column("street_number", sa.Integer(), nullable=True),
        sa.Column("suite", sa.String(length=10), nullable=True),
        sa.Column("address_info", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["nif"], ["clients.nif"], name="sites_nif_fkey"),
        sa.PrimaryKeyConstraint("id", name="sites_pkey"),
    )
    op.create_table(
        "certifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certifier_id", sa.Integer(), nullable=False),
        sa.Column("regulation_id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=80), nullable=True),
        sa.Column("inspection_date", sa.Date(), nullable=True),
        sa.Column("resolution_date", sa.Date(), nullable=True),
        sa.CheckConstraint("result IN ('Pass', 'Fail')", name="result_check"),
        sa.ForeignKeyConstraint(
            ["certifier_id"],
            ["certifiers.id"],
            name="certifications_certifier_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["regulation_id"],
            ["regulations.id"],
            name="certifications_regulation_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["site_id"],
            ["sites.id"],
            name="certifications_site_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="certifications_pkey"),
    )
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certification_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=300), nullable=False),
        sa.Column("description", sa.String(length=80), nullable=True),
        sa.Column("uploaded_at", sa.Date(), nullable=False),
        sa.Column("file_type", sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(
            ["certification_id"],
            ["certifications.id"],
            name="attachments_certification_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id", name="attachments_pkey"),
        sa.UniqueConstraint(
            "id", "certification_id", name="uq_attachment_id_certification_id"
        ),
    )
    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certification_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("finding", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["certification_id"],
            ["certifications.id"],
            name="findings_certification_id_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"], ["rules.id"], name="findings_rule_id_fkey"
        ),
        sa.PrimaryKeyConstraint("id", name="findings_pkey"),
        sa.UniqueConstraint(
            "id", "certification_id", name="uq_finding_id_certification_id"
        ),
    )
    op.create_table(
        "finding_attachments",
        sa.Column("finding_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Integer(), nullable=False),
        sa.Column("certification_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_id", "certification_id"],
            ["attachments.id", "attachments.certification_id"],
            name="fk_attachment_id_certification_id",
        ),
        sa.ForeignKeyConstraint(
            ["finding_id", "certification_id"],
            ["findings.id", "findings.certification_id"],
            name="fk_finding_id_certification_id",
        ),
        sa.PrimaryKeyConstraint(
            "finding_id", "attachment_id", name="finding_attachments_pkey"
        ),
    )


def downgrade() -> None:
    """Drop the original schema."""
    op.drop_table("finding_attachments")
    op.drop_table("findings")
    op.drop_table("attachments")
    op.drop_table("certifications")
    op.drop_table("sites")
    op.drop_table("rules")
    op.drop_table("regulations")
    op.drop_table("certifiers")
    op.drop_table("clients")
