"""Revision ID: 009
Revises: 008
Create Date: 2026-07-10

Seed public demo organization and account for hosted deployment.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEMO_ORG_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
DEMO_USER_ID = uuid.UUID("a0000000-0000-4000-8000-000000000002")
DEMO_PASSWORD_HASH = "$2b$12$5CZr.Mp7zjMklErNvL9wmOZnaV2qO5Z1pq2xe4oq8zbh43pDGdIT6"
NOW = datetime.now(UTC)


def upgrade() -> None:
    orgs = sa.table(
        "organizations",
        sa.column("id", sa.Uuid),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("created_at", sa.DateTime),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.Uuid),
        sa.column("email", sa.String),
        sa.column("hashed_password", sa.String),
        sa.column("full_name", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    members = sa.table(
        "organization_members",
        sa.column("id", sa.Uuid),
        sa.column("org_id", sa.Uuid),
        sa.column("user_id", sa.Uuid),
        sa.column("role", sa.String),
        sa.column("created_at", sa.DateTime),
    )

    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM organizations WHERE id = :id"),
        {"id": str(DEMO_ORG_ID)},
    ).first()
    if existing:
        return

    op.bulk_insert(
        orgs,
        [
            {
                "id": DEMO_ORG_ID,
                "name": "VoxForge Demo",
                "slug": "voxforge-demo",
                "created_at": NOW,
            }
        ],
    )
    op.bulk_insert(
        users,
        [
            {
                "id": DEMO_USER_ID,
                "email": "demo@voxforge.io",
                "hashed_password": DEMO_PASSWORD_HASH,
                "full_name": "VoxForge Demo User",
                "is_active": True,
                "created_at": NOW,
                "updated_at": NOW,
            }
        ],
    )
    op.bulk_insert(
        members,
        [
            {
                "id": uuid.uuid4(),
                "org_id": DEMO_ORG_ID,
                "user_id": DEMO_USER_ID,
                "role": "owner",
                "created_at": NOW,
            }
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM organization_members WHERE org_id = :org_id"),
        {"org_id": str(DEMO_ORG_ID)},
    )
    bind.execute(sa.text("DELETE FROM users WHERE id = :id"), {"id": str(DEMO_USER_ID)})
    bind.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": str(DEMO_ORG_ID)})
