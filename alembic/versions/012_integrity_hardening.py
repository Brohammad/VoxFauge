"""Revision ID: 012
Revises: 011
Create Date: 2026-07-10

Integrity hardening: unique constraints for knowledge chunks and handoff snapshots.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DELETE FROM knowledge_chunks a
            USING knowledge_chunks b
            WHERE a.id > b.id
              AND a.document_version_id = b.document_version_id
              AND a.chunk_index = b.chunk_index
            """
        )
        op.execute(
            """
            DELETE FROM conversation_snapshots a
            USING conversation_snapshots b
            WHERE a.id > b.id
              AND a.handoff_id = b.handoff_id
            """
        )

    op.create_unique_constraint(
        "uq_knowledge_chunks_version_index",
        "knowledge_chunks",
        ["document_version_id", "chunk_index"],
    )
    op.create_unique_constraint(
        "uq_conversation_snapshots_handoff",
        "conversation_snapshots",
        ["handoff_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_conversation_snapshots_handoff", "conversation_snapshots", type_="unique"
    )
    op.drop_constraint(
        "uq_knowledge_chunks_version_index", "knowledge_chunks", type_="unique"
    )
