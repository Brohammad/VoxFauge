"""Revision ID: 011
Revises: 010
Create Date: 2026-07-10

Enterprise human handoff tables and session extensions.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "handoff_records",
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
        sa.Column("ticket_id", sa.String(128), nullable=True),
        sa.Column("ticket_provider", sa.String(32), nullable=False, server_default="mock"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(64), nullable=False),
        sa.Column("trigger_reason", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("replay_url", sa.String(2048), nullable=True),
        sa.Column("replay_token", sa.String(128), nullable=True),
        sa.Column(
            "assigned_to_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_to_email", sa.String(255), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", name="uq_handoff_records_session"),
    )
    op.create_index("idx_handoff_records_org_status", "handoff_records", ["org_id", "status"])
    op.create_index(
        "idx_handoff_records_assigned", "handoff_records", ["assigned_to_user_id", "status"]
    )

    op.create_table(
        "handoff_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_handoff_events_handoff", "handoff_events", ["handoff_id", "created_at"])

    op.create_table(
        "conversation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column(
        "voice_sessions",
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("voice_sessions", sa.Column("handoff_status", sa.String(32), nullable=True))
    op.add_column(
        "tool_calls",
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "outcome_kpis",
        sa.Column(
            "handoff_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("handoff_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("outcome_kpis", "handoff_id")
    op.drop_column("tool_calls", "handoff_id")
    op.drop_column("voice_sessions", "handoff_status")
    op.drop_column("voice_sessions", "handoff_id")
    op.drop_table("conversation_snapshots")
    op.drop_table("handoff_events")
    op.drop_table("handoff_records")
