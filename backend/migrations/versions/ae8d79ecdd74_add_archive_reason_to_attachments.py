"""Add archive_reason to attachments

Revision ID: ae8d79ecdd74
Revises: 14c5bde199e1
Create Date: 2026-05-07 10:32:53.987300

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ae8d79ecdd74"
down_revision: str | Sequence[str] | None = "14c5bde199e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "attachments", sa.Column("archive_reason", sa.String(160), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("attachments", "archive_reason")
