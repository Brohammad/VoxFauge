"""Revision ID: 008
Revises: 007
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saml_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_type", sa.String(32), nullable=False, server_default="generic"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("idp_entity_id", sa.String(255), nullable=False),
        sa.Column("idp_sso_url", sa.String(512), nullable=False),
        sa.Column("idp_x509_cert", sa.Text(), nullable=False),
        sa.Column("sp_entity_id", sa.String(255), nullable=False),
        sa.Column("acs_url", sa.String(512), nullable=False),
        sa.Column("default_role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("role_mapping_rules", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_saml_connections_org_id", "saml_connections", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_saml_connections_org_id", table_name="saml_connections")
    op.drop_table("saml_connections")
