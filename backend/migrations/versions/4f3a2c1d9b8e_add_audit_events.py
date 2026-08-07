"""add audit events

Revision ID: 4f3a2c1d9b8e
Revises: be69efd1411e
Create Date: 2026-08-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f3a2c1d9b8e"
down_revision: str | Sequence[str] | None = "be69efd1411e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "action IN ('finding.created', 'finding.archived', "
            "'finding.restored', 'attachment.uploaded', 'attachment.downloaded', "
            "'certification.created', 'certification.archived', "
            "'certification.restored', 'record.archived', 'record.restored', "
            "'ai.analysis_requested', 'user.created', 'login.success', "
            "'login.failed', 'authorization.failed')",
            name=op.f("ck_audit_events_action_check"),
        ),
        sa.CheckConstraint(
            "target_type IN ('finding', 'attachment', 'certification', "
            "'record', 'ai', 'user', 'auth')",
            name=op.f("ck_audit_events_target_type_check"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_actor_email",
        "audit_events",
        ["actor_email"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_action",
        "audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_created_at",
        "audit_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_events_target_type_target_id",
        "audit_events",
        ["target_type", "target_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_events_target_type_target_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_email", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_table("audit_events")
