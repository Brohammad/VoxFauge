"""Mock assignment provider for development and tests."""

from __future__ import annotations

from uuid import UUID

from voxforge.core.domain.handoff import AssignmentStrategy, HandoffAssignment


class MockAssignmentProvider:
    async def assign(
        self,
        *,
        org_id: UUID,
        handoff_id: UUID,
        strategy: AssignmentStrategy,
        intent: str | None = None,
    ) -> HandoffAssignment:
        _ = org_id, intent
        return HandoffAssignment(
            handoff_id=handoff_id,
            assignee_email="agent@voxforge.io",
            strategy=strategy,
            queue_position=1,
        )
