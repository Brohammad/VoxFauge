"""Revision ID: 006
Revises: 005
Create Date: 2026-07-08
"""

from collections.abc import Sequence
from datetime import UTC, datetime
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "support_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("prompt_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("tool_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("eval_thresholds", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_support_templates_slug", "support_templates", ["slug"])

    op.create_table(
        "onboarding_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "test_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_onboarding_runs_org_id", "onboarding_runs", ["org_id"])

    op.create_table(
        "outcome_kpis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("intent", sa.String(128), nullable=False),
        sa.Column("task_success", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escalation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("resolution_time_seconds", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_outcome_kpis_session"),
    )
    op.create_index("ix_outcome_kpis_org_id", "outcome_kpis", ["org_id"])
    op.create_index("ix_outcome_kpis_intent", "outcome_kpis", ["intent"])

    support_template_table = sa.table(
        "support_templates",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("prompt_config", sa.JSON()),
        sa.column("tool_config", sa.JSON()),
        sa.column("eval_thresholds", sa.JSON()),
        sa.column("is_default", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        support_template_table,
        [
            {
                "id": uuid.uuid4(),
                "name": "Customer Support Deflection",
                "slug": "customer-support-deflection",
                "prompt_config": {
                    "system_prompt": "You are a support voice agent focused on rapid resolution and safe escalation.",
                    "style": "concise, empathetic, policy-safe",
                },
                "tool_config": {
                    "enabled_tools": ["knowledge_base_lookup", "ticket_lookup", "ticket_create"],
                    "fallback_to_human": True,
                },
                "eval_thresholds": {
                    "task_success_min": 0.8,
                    "quality_min": 0.75,
                    "escalation_max": 0.35,
                },
                "is_default": True,
                "created_at": datetime.now(UTC),
            }
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_kpis_intent", table_name="outcome_kpis")
    op.drop_index("ix_outcome_kpis_org_id", table_name="outcome_kpis")
    op.drop_table("outcome_kpis")
    op.drop_index("ix_onboarding_runs_org_id", table_name="onboarding_runs")
    op.drop_table("onboarding_runs")
    op.drop_index("ix_support_templates_slug", table_name="support_templates")
    op.drop_table("support_templates")
