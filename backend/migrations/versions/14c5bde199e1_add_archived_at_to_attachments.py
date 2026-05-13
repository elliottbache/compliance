"""Add archived_at to attachments

Revision ID: 14c5bde199e1
Revises: 0eefc6ce8746
Create Date: 2026-05-07 03:51:50.092835

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14c5bde199e1"
down_revision: str | Sequence[str] | None = "0eefc6ce8746"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("attachments", sa.Column("archived_at", sa.DateTime, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("attachments", "archived_at")
