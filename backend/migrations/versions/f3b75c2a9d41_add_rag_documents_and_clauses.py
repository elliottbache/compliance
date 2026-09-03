"""add rag documents and clauses

Revision ID: f3b75c2a9d41
Revises: 4f3a2c1d9b8e
Create Date: 2026-09-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3b75c2a9d41"
down_revision: str | Sequence[str] | None = "4f3a2c1d9b8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("jurisdiction", sa.String(length=80), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_documents")),
        sa.UniqueConstraint("source_id", name=op.f("uq_rag_documents_source_id")),
    )
    op.create_index(
        "ix_rag_documents_source_id",
        "rag_documents",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        "ix_rag_documents_source_kind",
        "rag_documents",
        ["source_kind"],
        unique=False,
    )
    op.create_index(
        "ix_rag_documents_status",
        "rag_documents",
        ["status"],
        unique=False,
    )

    op.create_table(
        "rag_clauses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("citation_ref", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("path_text", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("sort_key", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["rag_documents.id"],
            name=op.f("fk_rag_clauses_document_id_rag_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_clauses")),
        sa.UniqueConstraint(
            "document_id",
            "content_hash",
            name=op.f("uq_rag_clauses_document_id_content_hash"),
        ),
        sa.UniqueConstraint(
            "document_id",
            "sort_key",
            name=op.f("uq_rag_clauses_document_id_sort_key"),
        ),
    )
    op.create_index(
        "ix_rag_clauses_document_id",
        "rag_clauses",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_rag_clauses_content_hash",
        "rag_clauses",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_rag_clauses_document_id_sort_key",
        "rag_clauses",
        ["document_id", "sort_key"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rag_clauses_document_id_sort_key", table_name="rag_clauses")
    op.drop_index("ix_rag_clauses_content_hash", table_name="rag_clauses")
    op.drop_index("ix_rag_clauses_document_id", table_name="rag_clauses")
    op.drop_table("rag_clauses")
    op.drop_index("ix_rag_documents_status", table_name="rag_documents")
    op.drop_index("ix_rag_documents_source_kind", table_name="rag_documents")
    op.drop_index("ix_rag_documents_source_id", table_name="rag_documents")
    op.drop_table("rag_documents")
