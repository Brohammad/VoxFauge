"""Revision ID: 007
Revises: 006
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_config_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("prompt_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("orchestrator_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("eval_thresholds", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "version", name="uq_agent_config_versions_org_version"),
    )
    op.create_index("ix_agent_config_versions_org_id", "agent_config_versions", ["org_id"])
    op.create_index(
        "ix_agent_config_versions_org_active",
        "agent_config_versions",
        ["org_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_config_versions_org_active", table_name="agent_config_versions")
    op.drop_index("ix_agent_config_versions_org_id", table_name="agent_config_versions")
    op.drop_table("agent_config_versions")
