"""make uploaded_at nullable in attachments

Revision ID: 561e6f89ce9e
Revises: 1dd66f244dea
Create Date: 2026-05-14 17:35:46.437729

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "561e6f89ce9e"
down_revision: str | Sequence[str] | None = "1dd66f244dea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "attachments",
        "uploaded_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "attachments",
        "uploaded_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
