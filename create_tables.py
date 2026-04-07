from datetime import date
from pydantic import BaseModel, Field, validate_call
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, Integer, String, UniqueConstraint, ForeignKey, Date, CheckConstraint, ForeignKeyConstraint
from sqlalchemy import select, insert
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column


DB_NAME = "compliance_db"
DB_URL = "postgresql+psycopg2://postgres:postgres@localhost/" + DB_NAME

engine = create_engine(DB_URL)
meta = MetaData()


def create_clients_table() -> None:
    """Create clients table with the module-level MetaData object."""
    clients_table = Table(
        "clients",
        meta,
        Column("nif", String(9), primary_key=True),
        Column("company_name", String(80)),
        Column("contact_name", String(80), nullable=False),
        Column("email", String(80)),
        Column("telephone", Integer),
        UniqueConstraint("company_name", name="uq_company_name")
    )


def create_sites_table() -> None:
    """Create sites table with the module-level MetaData object."""
    sites_table = Table(
        "sites",
        meta,
        Column("id", Integer, primary_key=True),
        Column("nif", ForeignKey("clients.nif"), nullable=False),
        Column("city", String(40), nullable=False),
        Column("postal_code", Integer, nullable=False),
        Column("street", String(40), nullable=False),
        Column("street_number", Integer),
        Column("suite", String(10)),
        Column("address_info", String(80)),
    )


def create_certifiers_table():
    """Create certifiers table with the module-level MetaData object."""
    certifiers_table = Table(
        "certifiers",
        meta,
        Column("id", Integer, primary_key=True),
        Column("organization_name", String(80), nullable=False),
        UniqueConstraint("organization_name", name="uq_organization_name")
    )


def create_regulations_table():
    """Create regulations table with the module-level MetaData object."""
    regulations_table = Table(
        "regulations",
        meta,
        Column("id", Integer, primary_key=True),
        Column("title", String(80), nullable=False),
        Column("description", String),
        Column("published_date", Date),
        UniqueConstraint("title", name="uq_title")
    )


def create_rules_table():
    """Create rules table with the module-level MetaData object."""
    rules_table = Table(
        "rules",
        meta,
        Column("id", Integer, primary_key=True),
        Column("regulation_id", ForeignKey("regulations.id"), nullable=False),
        Column("rule_index", String(10), nullable=False),
        Column("title", String(80)),
        Column("description", String),
        UniqueConstraint("regulation_id", "rule_index", name="uq_regulation_id_rule_index")
    )


def create_certifications_table():
    """Create certifications table with the module-level MetaData object."""
    certifications_table = Table(
        "certifications",
        meta,
        Column("id", Integer, primary_key=True),
        Column("certifier_id", ForeignKey("certifiers.id"), nullable=False),
        Column("regulation_id", ForeignKey("regulations.id"), nullable=False),
        Column("site_id", ForeignKey("sites.id"), nullable=False),
        Column("result", String(80)),
        Column("inspection_date", Date),
        Column("resolution_date", Date),
        CheckConstraint("result IN ('Pass', 'Fail')", name="result_check")
    )


def create_attachments_table():
    """Create attachments table with the module-level MetaData object."""
    attachments_table = Table(
        "attachments",
        meta,
        Column("id", Integer, primary_key=True),
        Column("file_type", String(80), nullable=False),
        Column("certification_id", ForeignKey("certifications.id"), nullable=False),
        Column("file_path", String(300), nullable=False),
        Column("description", String(80)),
        Column("uploaded_at", Date, nullable=False),
        UniqueConstraint("id", "certification_id", name="uq_attachment_id_certification_id")
    )


def create_findings_table():
    """Create inspection findings table with the module-level MetaData object."""
    findings_table = Table(
        "findings",
        meta,
        Column("id", Integer, primary_key=True),
        Column("certification_id", ForeignKey("certifications.id"), nullable=False),
        Column("rule_id", ForeignKey("rules.id"), nullable=False),
        Column("finding", String, nullable=False),
        UniqueConstraint("id", "certification_id", name="uq_finding_id_certification_id")
    )


def create_finding_attachments_table():
    """Create join table between findings and attachments with the module-level MetaData object."""
    finding_attachments_table = Table(
        "finding_attachments",
        meta,
        Column("finding_id", Integer, nullable=False, primary_key=True),
        Column("attachment_id", Integer, nullable=False, primary_key=True),
        Column("certification_id", Integer, nullable=False),
        ForeignKeyConstraint(
            ["finding_id", "certification_id"],
            ["findings.id", "findings.certification_id"],
            name="fk_finding_id_certification_id"
        ),
        ForeignKeyConstraint(
            ["attachment_id", "certification_id"],
            ["attachments.id", "attachments.certification_id"],
            name="fk_attachment_id_certification_id"
        )
    )


if __name__ == "__main__":
    create_clients_table()
    create_sites_table()
    create_certifiers_table()
    create_regulations_table()
    create_rules_table()
    create_certifications_table()
    create_findings_table()
    create_attachments_table()
    create_finding_attachments_table()
    meta.drop_all(engine)
    meta.create_all(engine)
