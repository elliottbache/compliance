from datetime import date

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from compliance.db.db_access import convention


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    metadata = MetaData(naming_convention=convention)


class Client(Base):
    """Represents an organization that owns one or more compliance sites."""

    __tablename__ = "clients"

    nif: Mapped[str] = mapped_column(String(9), primary_key=True, autoincrement=False)
    company_name: Mapped[str | None] = mapped_column(unique=True)
    contact_name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str | None] = mapped_column(String(80))
    telephone: Mapped[int | None]

    client_site_rel: Mapped[list["Site"]] = relationship(
        back_populates="site_client_rel"
    )


class Site(Base):
    """Represents a physical site that can receive compliance certifications."""

    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    nif: Mapped[str] = mapped_column(String(9), ForeignKey("clients.nif"))
    city: Mapped[str] = mapped_column(String(40))
    postal_code: Mapped[int]
    street: Mapped[str] = mapped_column(String(40))
    street_number: Mapped[int | None]
    suite: Mapped[str | None] = mapped_column(String(10))
    address_info: Mapped[str | None] = mapped_column(String(80))

    site_client_rel: Mapped["Client"] = relationship(back_populates="client_site_rel")
    site_certification_rel: Mapped[list["Certification"]] = relationship(
        back_populates="certification_site_rel"
    )


class Certifier(Base):
    """Represents an organization that performs compliance certifications."""

    __tablename__ = "certifiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_name: Mapped[str] = mapped_column(String(80), unique=True)

    certifier_certification_rel: Mapped[list["Certification"]] = relationship(
        back_populates="certification_certifier_rel"
    )


class Regulation(Base):
    """Represents a regulation that defines compliance requirements."""

    __tablename__ = "regulations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None]
    published_date: Mapped[date | None]

    regulation_rule_rel: Mapped[list["Rule"]] = relationship(
        back_populates="rule_regulation_rel"
    )
    regulation_certification_rel: Mapped[list["Certification"]] = relationship(
        back_populates="certification_regulation_rel"
    )


class Rule(Base):
    """Represents an individual rule within a regulation."""

    __tablename__ = "rules"
    __table_args__ = (
        UniqueConstraint(
            "regulation_id", "rule_index", name="uq_rules_regulation_id_rule_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    regulation_id: Mapped[int] = mapped_column(ForeignKey("regulations.id"))
    rule_index: Mapped[str] = mapped_column(String(10))
    title: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None]

    rule_regulation_rel: Mapped["Regulation"] = relationship(
        back_populates="regulation_rule_rel"
    )
    rule_finding_rel: Mapped[list["Finding"]] = relationship(
        back_populates="finding_rule_rel"
    )


class Certification(Base):
    """Represents one site certification against a regulation."""

    __tablename__ = "certifications"
    __table_args__ = (
        CheckConstraint("result IN ('Pass', 'Fail')", name="result_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    certifier_id: Mapped[int] = mapped_column(ForeignKey("certifiers.id"))
    regulation_id: Mapped[int] = mapped_column(ForeignKey("regulations.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    result: Mapped[str | None] = mapped_column(String(80))
    inspection_date: Mapped[date | None]
    resolution_date: Mapped[date | None]

    certification_certifier_rel: Mapped["Certifier"] = relationship(
        back_populates="certifier_certification_rel"
    )
    certification_regulation_rel: Mapped["Regulation"] = relationship(
        back_populates="regulation_certification_rel"
    )
    certification_site_rel: Mapped["Site"] = relationship(
        back_populates="site_certification_rel"
    )
    certification_attachment_rel: Mapped[list["Attachment"]] = relationship(
        back_populates="attachment_certification_rel"
    )
    certification_finding_rel: Mapped[list["Finding"]] = relationship(
        back_populates="finding_certification_rel"
    )


class Attachment(Base):
    """Represents a file attached to a certification record."""

    __tablename__ = "attachments"
    __table_args__ = (
        UniqueConstraint(
            "id", "certification_id", name="uq_attachments_id_certification_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    file_type: Mapped[str] = mapped_column(String(80))
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"))
    file_path: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(String(80))
    uploaded_at: Mapped[date]

    attachment_certification_rel: Mapped["Certification"] = relationship(
        back_populates="certification_attachment_rel"
    )


class Finding(Base):
    """Represents a compliance finding tied to a certification and rule."""

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint(
            "id", "certification_id", name="uq_findings_id_certification_id"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    certification_id: Mapped[int] = mapped_column(ForeignKey("certifications.id"))
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"))
    finding: Mapped[str]

    finding_certification_rel: Mapped["Certification"] = relationship(
        back_populates="certification_finding_rel"
    )
    finding_rule_rel: Mapped["Rule"] = relationship(back_populates="rule_finding_rel")


class FindingAttachment(Base):
    """Links findings to supporting attachments within one certification."""

    __tablename__ = "finding_attachments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["finding_id", "certification_id"],
            ["findings.id", "findings.certification_id"],
            name="fk_finding_attachments_finding_id_id_certification_id_certification_id",
        ),
        ForeignKeyConstraint(
            ["attachment_id", "certification_id"],
            ["attachments.id", "attachments.certification_id"],
            name="fk_finding_attachments_attachment_id_id_certification_id_certification_id",
        ),
    )

    finding_id: Mapped[int] = mapped_column(primary_key=True)
    attachment_id: Mapped[int] = mapped_column(primary_key=True)
    certification_id: Mapped[int]
