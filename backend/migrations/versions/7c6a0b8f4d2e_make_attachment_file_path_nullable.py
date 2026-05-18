"""make attachment file_path nullable

Revision ID: 7c6a0b8f4d2e
Revises: 63e611c60280
Create Date: 2026-05-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c6a0b8f4d2e"
down_revision: str | Sequence[str] | None = "63e611c60280"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow attachment metadata to exist before a file is uploaded."""
    op.alter_column(
        "attachments",
        "file_path",
        existing_type=sa.String(length=300),
        nullable=True,
    )


def downgrade() -> None:
    """Require every attachment row to have a stored file path."""
    op.alter_column(
        "attachments",
        "file_path",
        existing_type=sa.String(length=300),
        nullable=False,
    )
