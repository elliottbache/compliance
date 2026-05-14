"""remove file_type from attachments

Revision ID: 1dd66f244dea
Revises: 0bb2da337c8e
Create Date: 2026-05-14 12:12:09.294132

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1dd66f244dea"
down_revision: str | Sequence[str] | None = "0bb2da337c8e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("attachments", "file_type")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("attachments", sa.Column("file_type", sa.String(80), nullable=False))
