"""Round-robin assignment across org members."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.auth import OrgRole
from voxforge.core.domain.handoff import AssignmentStrategy, HandoffAssignment
from voxforge.infrastructure.db.models import HandoffRecordModel, OrganizationMemberModel, UserModel


class RoundRobinAssignmentProvider:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._cursor: dict[UUID, int] = {}

    async def assign(
        self,
        *,
        org_id: UUID,
        handoff_id: UUID,
        strategy: AssignmentStrategy,
        intent: str | None = None,
    ) -> HandoffAssignment:
        _ = intent
        members = (
            await self._session.execute(
                select(UserModel)
                .join(OrganizationMemberModel, OrganizationMemberModel.user_id == UserModel.id)
                .where(
                    OrganizationMemberModel.org_id == org_id,
                    OrganizationMemberModel.role.in_(
                        [OrgRole.OWNER.value, OrgRole.ADMIN.value, OrgRole.MEMBER.value]
                    ),
                )
                .order_by(UserModel.created_at.asc())
            )
        ).scalars().all()

        if not members:
            return HandoffAssignment(handoff_id=handoff_id, strategy=strategy)

        last_assigned = (
            await self._session.execute(
                select(HandoffRecordModel)
                .where(
                    HandoffRecordModel.org_id == org_id,
                    HandoffRecordModel.assigned_to_user_id.is_not(None),
                )
                .order_by(HandoffRecordModel.assigned_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        if last_assigned and last_assigned.assigned_to_user_id:
            ids = [m.id for m in members]
            try:
                idx = ids.index(last_assigned.assigned_to_user_id)
                next_user = members[(idx + 1) % len(members)]
            except ValueError:
                next_user = members[0]
        else:
            cursor = self._cursor.get(org_id, -1)
            next_user = members[(cursor + 1) % len(members)]
            self._cursor[org_id] = (cursor + 1) % len(members)

        return HandoffAssignment(
            handoff_id=handoff_id,
            assignee_user_id=next_user.id,
            assignee_email=next_user.email,
            strategy=strategy,
        )
