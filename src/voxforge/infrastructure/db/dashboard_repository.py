from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.dashboard import (
    ActivityItem,
    DashboardOverview,
    EvaluationSummary,
    LatencyBucket,
    SessionSummaryItem,
)
from voxforge.core.domain.evaluation import MetricName
from voxforge.infrastructure.db.models import (
    EvaluationMetricModel,
    EvaluationRunModel,
    MessageModel,
    SessionMetricModel,
    ToolCallModel,
    VoiceSessionModel,
)


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_overview(self, org_id: UUID) -> DashboardOverview:
        sessions_q = select(func.count()).select_from(VoiceSessionModel).where(
            VoiceSessionModel.org_id == org_id
        )
        active_q = select(func.count()).select_from(VoiceSessionModel).where(
            VoiceSessionModel.org_id == org_id,
            VoiceSessionModel.status == "active",
        )
        completed_q = select(func.count()).select_from(VoiceSessionModel).where(
            VoiceSessionModel.org_id == org_id,
            VoiceSessionModel.status == "completed",
        )
        messages_q = (
            select(func.count())
            .select_from(MessageModel)
            .join(VoiceSessionModel, MessageModel.session_id == VoiceSessionModel.id)
            .where(VoiceSessionModel.org_id == org_id)
        )
        tools_q = select(func.count()).select_from(ToolCallModel).where(
            ToolCallModel.org_id == org_id
        )
        evals_q = select(func.count()).select_from(EvaluationRunModel).where(
            EvaluationRunModel.org_id == org_id
        )
        avg_e2e_q = (
            select(func.avg(SessionMetricModel.value_ms))
            .join(VoiceSessionModel, SessionMetricModel.session_id == VoiceSessionModel.id)
            .where(
                VoiceSessionModel.org_id == org_id,
                SessionMetricModel.metric_name == "e2e_ms",
            )
        )
        avg_score_q = select(func.avg(EvaluationRunModel.overall_score)).where(
            EvaluationRunModel.org_id == org_id
        )
        failed_q = select(func.count()).select_from(EvaluationRunModel).where(
            EvaluationRunModel.org_id == org_id,
            EvaluationRunModel.overall_status == "failed",
        )
        cost_q = (
            select(func.sum(EvaluationMetricModel.value))
            .join(EvaluationRunModel, EvaluationMetricModel.run_id == EvaluationRunModel.id)
            .where(
                EvaluationRunModel.org_id == org_id,
                EvaluationMetricModel.name == MetricName.COST.value,
            )
        )

        total_sessions = int((await self._session.execute(sessions_q)).scalar_one())
        active_sessions = int((await self._session.execute(active_q)).scalar_one())
        completed_sessions = int((await self._session.execute(completed_q)).scalar_one())
        total_messages = int((await self._session.execute(messages_q)).scalar_one())
        total_tool_calls = int((await self._session.execute(tools_q)).scalar_one())
        total_evaluations = int((await self._session.execute(evals_q)).scalar_one())
        avg_e2e = (await self._session.execute(avg_e2e_q)).scalar_one()
        avg_score = (await self._session.execute(avg_score_q)).scalar_one()
        failed_evaluations = int((await self._session.execute(failed_q)).scalar_one())
        total_cost = (await self._session.execute(cost_q)).scalar_one()

        return DashboardOverview(
            total_sessions=total_sessions,
            active_sessions=active_sessions,
            completed_sessions=completed_sessions,
            total_messages=total_messages,
            total_tool_calls=total_tool_calls,
            total_evaluations=total_evaluations,
            avg_e2e_latency_ms=float(avg_e2e) if avg_e2e is not None else None,
            avg_evaluation_score=float(avg_score) if avg_score is not None else None,
            failed_evaluations=failed_evaluations,
            estimated_total_cost_usd=float(total_cost) if total_cost is not None else None,
        )

    async def get_recent_sessions(
        self, org_id: UUID, *, limit: int = 20
    ) -> list[SessionSummaryItem]:
        result = await self._session.execute(
            select(VoiceSessionModel)
            .where(VoiceSessionModel.org_id == org_id)
            .order_by(VoiceSessionModel.started_at.desc())
            .limit(limit)
        )
        sessions = result.scalars().all()
        items: list[SessionSummaryItem] = []

        for s in sessions:
            msg_count = int(
                (
                    await self._session.execute(
                        select(func.count())
                        .select_from(MessageModel)
                        .where(MessageModel.session_id == s.id)
                    )
                ).scalar_one()
            )
            avg_e2e = (
                await self._session.execute(
                    select(func.avg(SessionMetricModel.value_ms)).where(
                        SessionMetricModel.session_id == s.id,
                        SessionMetricModel.metric_name == "e2e_ms",
                    )
                )
            ).scalar_one()
            last_eval = (
                await self._session.execute(
                    select(EvaluationRunModel.overall_score)
                    .where(EvaluationRunModel.session_id == s.id)
                    .order_by(EvaluationRunModel.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            items.append(
                SessionSummaryItem(
                    id=s.id,
                    status=s.status,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    message_count=msg_count,
                    avg_e2e_ms=float(avg_e2e) if avg_e2e is not None else None,
                    last_evaluation_score=float(last_eval) if last_eval is not None else None,
                )
            )
        return items

    async def get_latency_stats(self, org_id: UUID) -> list[LatencyBucket]:
        metrics = ["stt_ms", "llm_first_token_ms", "tts_first_byte_ms", "e2e_ms"]
        buckets: list[LatencyBucket] = []

        for name in metrics:
            avg_q = (
                select(func.avg(SessionMetricModel.value_ms))
                .join(VoiceSessionModel, SessionMetricModel.session_id == VoiceSessionModel.id)
                .where(VoiceSessionModel.org_id == org_id, SessionMetricModel.metric_name == name)
            )
            count_q = (
                select(func.count())
                .select_from(SessionMetricModel)
                .join(VoiceSessionModel, SessionMetricModel.session_id == VoiceSessionModel.id)
                .where(VoiceSessionModel.org_id == org_id, SessionMetricModel.metric_name == name)
            )
            avg_val = (await self._session.execute(avg_q)).scalar_one()
            count_val = int((await self._session.execute(count_q)).scalar_one())
            if count_val == 0:
                continue
            buckets.append(
                LatencyBucket(
                    metric_name=name,
                    avg_ms=round(float(avg_val), 1),
                    sample_count=count_val,
                )
            )
        return buckets

    async def get_evaluation_summary(self, org_id: UUID) -> EvaluationSummary:
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(EvaluationRunModel)
                    .where(EvaluationRunModel.org_id == org_id)
                )
            ).scalar_one()
        )
        avg_score = (
            await self._session.execute(
                select(func.avg(EvaluationRunModel.overall_score)).where(
                    EvaluationRunModel.org_id == org_id
                )
            )
        ).scalar_one()

        status_counts: dict[str, int] = {}
        for status in ("passed", "warning", "failed"):
            count = int(
                (
                    await self._session.execute(
                        select(func.count())
                        .select_from(EvaluationRunModel)
                        .where(
                            EvaluationRunModel.org_id == org_id,
                            EvaluationRunModel.overall_status == status,
                        )
                    )
                ).scalar_one()
            )
            status_counts[status] = count

        by_metric: dict[str, float] = {}
        for metric_name in MetricName:
            avg = (
                await self._session.execute(
                    select(func.avg(EvaluationMetricModel.score))
                    .join(EvaluationRunModel, EvaluationMetricModel.run_id == EvaluationRunModel.id)
                    .where(
                        EvaluationRunModel.org_id == org_id,
                        EvaluationMetricModel.name == metric_name.value,
                    )
                )
            ).scalar_one()
            if avg is not None:
                by_metric[metric_name.value] = round(float(avg), 3)

        return EvaluationSummary(
            total_runs=total,
            avg_score=round(float(avg_score), 3) if avg_score is not None else None,
            passed=status_counts.get("passed", 0),
            warning=status_counts.get("warning", 0),
            failed=status_counts.get("failed", 0),
            by_metric=by_metric,
        )

    async def get_recent_activity(
        self, org_id: UUID, *, limit: int = 30
    ) -> list[ActivityItem]:
        since = datetime.now(UTC) - timedelta(days=7)
        items: list[ActivityItem] = []

        evals = await self._session.execute(
            select(EvaluationRunModel)
            .where(EvaluationRunModel.org_id == org_id, EvaluationRunModel.created_at >= since)
            .order_by(EvaluationRunModel.created_at.desc())
            .limit(limit)
        )
        for e in evals.scalars():
            items.append(
                ActivityItem(
                    type="evaluation",
                    timestamp=e.created_at,
                    session_id=e.session_id,
                    summary=f"Score {e.overall_score:.2f} — {e.overall_status}",
                    status=e.overall_status,
                )
            )

        tools = await self._session.execute(
            select(ToolCallModel)
            .where(ToolCallModel.org_id == org_id, ToolCallModel.created_at >= since)
            .order_by(ToolCallModel.created_at.desc())
            .limit(limit)
        )
        for t in tools.scalars():
            items.append(
                ActivityItem(
                    type="tool_call",
                    timestamp=t.created_at,
                    session_id=t.session_id,
                    summary=f"{t.tool_name}: {t.status}",
                    status=t.status,
                )
            )

        sessions = await self._session.execute(
            select(VoiceSessionModel)
            .where(VoiceSessionModel.org_id == org_id, VoiceSessionModel.started_at >= since)
            .order_by(VoiceSessionModel.started_at.desc())
            .limit(limit)
        )
        for s in sessions.scalars():
            items.append(
                ActivityItem(
                    type="session",
                    timestamp=s.started_at,
                    session_id=s.id,
                    summary=f"Session {s.status}",
                    status=s.status,
                )
            )

        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[:limit]
