"""Add archived_at and archive_reason to clients, sites, certifiers, regulations, rules, certifications, and findings

Revision ID: 1b5fa38b3284
Revises: ae8d79ecdd74
Create Date: 2026-05-07 10:40:13.375049

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1b5fa38b3284"
down_revision: str | Sequence[str] | None = "ae8d79ecdd74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("clients", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column("clients", sa.Column("archive_reason", sa.String(160), nullable=True))
    op.add_column("sites", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column("sites", sa.Column("archive_reason", sa.String(160), nullable=True))
    op.add_column("certifiers", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column(
        "certifiers", sa.Column("archive_reason", sa.String(160), nullable=True)
    )
    op.add_column("regulations", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column(
        "regulations", sa.Column("archive_reason", sa.String(160), nullable=True)
    )
    op.add_column("rules", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column("rules", sa.Column("archive_reason", sa.String(160), nullable=True))
    op.add_column(
        "certifications", sa.Column("archived_at", sa.DateTime, nullable=True)
    )
    op.add_column(
        "certifications", sa.Column("archive_reason", sa.String(160), nullable=True)
    )
    op.add_column("findings", sa.Column("archived_at", sa.DateTime, nullable=True))
    op.add_column(
        "findings", sa.Column("archive_reason", sa.String(160), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("clients", "archived_at")
    op.drop_column("clients", "archive_reason")
    op.drop_column("sites", "archived_at")
    op.drop_column("sites", "archive_reason")
    op.drop_column("certifiers", "archived_at")
    op.drop_column("certifiers", "archive_reason")
    op.drop_column("regulations", "archived_at")
    op.drop_column("regulations", "archive_reason")
    op.drop_column("rules", "archived_at")
    op.drop_column("rules", "archive_reason")
    op.drop_column("certifications", "archived_at")
    op.drop_column("certifications", "archive_reason")
    op.drop_column("findings", "archived_at")
    op.drop_column("findings", "archive_reason")
