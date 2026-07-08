from uuid import UUID

from voxforge.core.domain.dashboard import (
    ActivityItem,
    DashboardOverview,
    EvaluationSummary,
    LatencyBucket,
    OutcomeSummary,
    SessionSummaryItem,
)
from voxforge.infrastructure.db.dashboard_repository import DashboardRepository


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self._repo = repository

    async def get_overview(self, org_id: UUID) -> DashboardOverview:
        return await self._repo.get_overview(org_id)

    async def get_recent_sessions(
        self, org_id: UUID, *, limit: int = 20
    ) -> list[SessionSummaryItem]:
        return await self._repo.get_recent_sessions(org_id, limit=limit)

    async def get_latency_stats(self, org_id: UUID) -> list[LatencyBucket]:
        return await self._repo.get_latency_stats(org_id)

    async def get_evaluation_summary(self, org_id: UUID) -> EvaluationSummary:
        return await self._repo.get_evaluation_summary(org_id)

    async def get_recent_activity(
        self, org_id: UUID, *, limit: int = 30
    ) -> list[ActivityItem]:
        return await self._repo.get_recent_activity(org_id, limit=limit)

    async def get_outcome_summary(self, org_id: UUID) -> OutcomeSummary:
        return await self._repo.get_outcome_summary(org_id)
