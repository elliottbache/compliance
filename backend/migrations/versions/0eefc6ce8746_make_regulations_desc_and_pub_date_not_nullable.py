"""Make regulations.description and regulations.published_date non-nullable

Revision ID: 0eefc6ce8746
Revises: 68c51a10a015
Create Date: 2026-05-06 22:53:47.773964

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0eefc6ce8746"
down_revision: str | Sequence[str] | None = "68c51a10a015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "regulations", "description", existing_type=sa.String(), nullable=False
    )
    op.alter_column(
        "regulations", "published_date", existing_type=sa.String(), nullable=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "regulations", "description", existing_type=sa.String(), nullable=True
    )
    op.alter_column(
        "regulations", "published_date", existing_type=sa.String(), nullable=True
    )
