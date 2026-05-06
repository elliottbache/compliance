"""Make rules.description non-nullable

Revision ID: 68c51a10a015
Revises: 
Create Date: 2026-05-06 22:20:25.004746

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "68c51a10a015"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("rules", "description", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("rules", "description", existing_type=sa.String(), nullable=True)
