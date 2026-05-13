"""change uploaded_at to timezone-aware UTC

Revision ID: 6ddc8fb3aa53
Revises: 9e77d299bc33
Create Date: 2026-05-08 09:30:06.981782

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6ddc8fb3aa53"
down_revision: str | Sequence[str] | None = "9e77d299bc33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Use postgresql_using to explicitly cast naive timestamps to UTC
    op.alter_column(
        "attachments",
        "uploaded_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        postgresql_using="uploaded_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "attachments",
        "uploaded_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
    )
