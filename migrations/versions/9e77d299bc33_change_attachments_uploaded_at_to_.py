"""change attachments uploaded_at to datetime

Revision ID: 9e77d299bc33
Revises: 1b5fa38b3284
Create Date: 2026-05-07 22:09:00.167823

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9e77d299bc33"
down_revision: str | Sequence[str] | None = "1b5fa38b3284"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "attachments",
        "uploaded_at",
        existing_type=sa.Date(),
        type_=sa.DateTime(),
        existing_nullable=False,
        postgresql_using="uploaded_at::timestamp",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "attachments",
        "uploaded_at",
        existing_type=sa.DateTime(),
        type_=sa.Date(),
        existing_nullable=False,
        postgresql_using="uploaded_at::date",
    )
