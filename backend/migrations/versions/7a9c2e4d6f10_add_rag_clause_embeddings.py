"""add rag clause embeddings

Revision ID: 7a9c2e4d6f10
Revises: f3b75c2a9d41
Create Date: 2026-09-29 00:00:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7a9c2e4d6f10"
down_revision: str | Sequence[str] | None = "f3b75c2a9d41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "rag_clause_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("clause_id", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.VECTOR(), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "dimensions > 0",
            name=op.f("ck_rag_clause_embeddings_positive_dimensions"),
        ),
        sa.CheckConstraint(
            "length(input_hash) = 64",
            name=op.f("ck_rag_clause_embeddings_input_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["clause_id"],
            ["rag_clauses.id"],
            name=op.f("fk_rag_clause_embeddings_clause_id_rag_clauses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_clause_embeddings")),
        sa.UniqueConstraint(
            "clause_id",
            name=op.f("uq_rag_clause_embeddings_clause_id"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("rag_clause_embeddings")
