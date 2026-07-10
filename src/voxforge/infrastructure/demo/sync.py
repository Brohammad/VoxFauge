"""Synchronize the public demo organization and account for hosted deployment."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings
from voxforge.infrastructure.db.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from voxforge.infrastructure.security.tokens import hash_password, verify_password


async def ensure_demo_account(session: AsyncSession, settings: Settings) -> None:
    """Ensure demo org, user, membership, and password match configured values."""
    org_id = UUID(settings.demo_org_id)
    user_id = UUID(settings.demo_user_id)
    now = datetime.now(UTC)

    org = await session.get(OrganizationModel, org_id)
    if org is None:
        session.add(
            OrganizationModel(
                id=org_id,
                name="VoxForge Demo",
                slug="voxforge-demo",
                created_at=now,
            )
        )
    else:
        org.name = "VoxForge Demo"
        org.slug = "voxforge-demo"

    user = await session.get(UserModel, user_id)
    if user is None:
        session.add(
            UserModel(
                id=user_id,
                email=settings.demo_email,
                hashed_password=hash_password(settings.demo_password_hint),
                full_name="VoxForge Demo User",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        user.email = settings.demo_email
        user.full_name = "VoxForge Demo User"
        user.is_active = True
        user.updated_at = now
        try:
            password_ok = verify_password(settings.demo_password_hint, user.hashed_password)
        except ValueError:
            password_ok = False
        if not password_ok:
            user.hashed_password = hash_password(settings.demo_password_hint)

    result = await session.execute(
        select(OrganizationMemberModel).where(
            OrganizationMemberModel.org_id == org_id,
            OrganizationMemberModel.user_id == user_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        session.add(
            OrganizationMemberModel(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                role="owner",
                created_at=now,
            )
        )
    elif membership.role != "owner":
        membership.role = "owner"

    await session.commit()
