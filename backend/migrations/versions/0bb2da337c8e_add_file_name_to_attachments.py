"""add file_name to attachments

Revision ID: 0bb2da337c8e
Revises: e9ecd6a43dad
Create Date: 2026-05-14 11:52:12.121043

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0bb2da337c8e"
down_revision: str | Sequence[str] | None = "e9ecd6a43dad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("attachments", sa.Column("file_name", sa.String(300), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("attachments", "file_name")
