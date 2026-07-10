"""Revision ID: 010
Revises: 009
Create Date: 2026-07-10

Enterprise knowledge base tables with pgvector chunk storage.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1536"),
        sa.Column("chunking_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "name", name="uq_knowledge_collections_org_name"),
    )
    op.create_index("ix_knowledge_collections_org_id", "knowledge_collections", ["org_id"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_collections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("active_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_documents_org_id", "knowledge_documents", ["org_id"])
    op.create_index(
        "ix_knowledge_documents_collection_id", "knowledge_documents", ["collection_id"]
    )

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("blob_path", sa.String(1024), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "document_id", "version_number", name="uq_knowledge_document_versions_doc_ver"
        ),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_chunks_org_id", "knowledge_chunks", ["org_id"])
    op.create_index(
        "ix_knowledge_chunks_document_version_id",
        "knowledge_chunks",
        ["document_version_id"],
    )

    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE knowledge_chunks ADD COLUMN embedding_vec vector(1536)"
        )
        op.execute(
            "CREATE INDEX idx_knowledge_chunks_embedding ON knowledge_chunks "
            "USING hnsw (embedding_vec vector_cosine_ops)"
        )

    op.create_table(
        "knowledge_ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_knowledge_ingest_jobs_status", "knowledge_ingest_jobs", ["status"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_knowledge_ingest_jobs_status", table_name="knowledge_ingest_jobs")
    op.drop_table("knowledge_ingest_jobs")

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_embedding")
        op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding_vec")

    op.drop_index("ix_knowledge_chunks_document_version_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_org_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")

    op.drop_table("knowledge_document_versions")

    op.drop_index("ix_knowledge_documents_collection_id", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_org_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_knowledge_collections_org_id", table_name="knowledge_collections")
    op.drop_table("knowledge_collections")
