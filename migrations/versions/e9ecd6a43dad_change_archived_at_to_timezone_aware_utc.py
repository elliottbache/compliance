"""change archived_at to timezone-aware UTC

Revision ID: e9ecd6a43dad
Revises: 6ddc8fb3aa53
Create Date: 2026-05-08 09:35:41.194402

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9ecd6a43dad"
down_revision: str | Sequence[str] | None = "6ddc8fb3aa53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

tables = [
    "attachments",
    "certifications",
    "certifiers",
    "clients",
    "findings",
    "regulations",
    "rules",
    "sites",
]


def upgrade() -> None:
    """Upgrade schema."""
    for table in tables:
        op.alter_column(
            table,
            "archived_at",
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            postgresql_using="archived_at AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in tables:
        op.alter_column(
            table,
            "archived_at",
            type_=sa.DateTime(timezone=False),
            existing_type=sa.DateTime(timezone=True),
        )
