"""Tests for demo account synchronization."""

from uuid import UUID

import pytest

from voxforge.config import Settings
from voxforge.infrastructure.db.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from voxforge.infrastructure.demo.sync import ensure_demo_account
from voxforge.infrastructure.security.tokens import verify_password

DEMO_ORG_ID = UUID("a0000000-0000-4000-8000-000000000001")
DEMO_USER_ID = UUID("a0000000-0000-4000-8000-000000000002")


def _demo_settings() -> Settings:
    return Settings(
        demo_enabled=True,
        demo_org_id=str(DEMO_ORG_ID),
        demo_user_id=str(DEMO_USER_ID),
        demo_email="demo@voxforge.io",
        demo_password_hint="VoxForgeDemo!",
    )


@pytest.mark.asyncio
async def test_ensure_demo_account_creates_records(db_session):
    settings = _demo_settings()

    await ensure_demo_account(db_session, settings)

    org = await db_session.get(OrganizationModel, DEMO_ORG_ID)
    user = await db_session.get(UserModel, DEMO_USER_ID)
    assert org is not None
    assert org.slug == "voxforge-demo"
    assert user is not None
    assert user.email == "demo@voxforge.io"
    assert verify_password("VoxForgeDemo!", user.hashed_password)

    members = await db_session.get(OrganizationMemberModel, user.memberships[0].id)
    assert members is not None
    assert members.role == "owner"


@pytest.mark.asyncio
async def test_ensure_demo_account_resets_password(db_session):
    settings = _demo_settings()
    await ensure_demo_account(db_session, settings)

    user = await db_session.get(UserModel, DEMO_USER_ID)
    user.hashed_password = "stale-hash"
    await db_session.commit()

    await ensure_demo_account(db_session, settings)

    user = await db_session.get(UserModel, DEMO_USER_ID)
    assert verify_password("VoxForgeDemo!", user.hashed_password)
