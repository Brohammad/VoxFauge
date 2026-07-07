from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from voxforge.core.domain.evaluation import (
    EvaluationMetric,
    EvaluationRun,
    EvaluationStatus,
    MetricName,
)
from voxforge.infrastructure.db.models import EvaluationMetricModel, EvaluationRunModel


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_run(
        self,
        *,
        org_id: UUID | None,
        session_id: UUID,
        user_transcript: str,
        assistant_response: str,
        overall_score: float,
        overall_status: EvaluationStatus,
        metrics: list[EvaluationMetric],
    ) -> EvaluationRun:
        run_id = uuid4()
        run_model = EvaluationRunModel(
            id=run_id,
            org_id=org_id,
            session_id=session_id,
            user_transcript=user_transcript,
            assistant_response=assistant_response,
            overall_score=overall_score,
            overall_status=overall_status.value,
        )
        self._session.add(run_model)

        for metric in metrics:
            self._session.add(
                EvaluationMetricModel(
                    run_id=run_id,
                    name=metric.name.value,
                    score=metric.score,
                    value=metric.value,
                    unit=metric.unit,
                    status=metric.status.value,
                    details=metric.details,
                )
            )

        await self._session.flush()
        return await self.get_run(run_id)

    async def get_run(self, run_id: UUID) -> EvaluationRun:
        result = await self._session.execute(
            select(EvaluationRunModel)
            .where(EvaluationRunModel.id == run_id)
            .options(selectinload(EvaluationRunModel.metrics))
        )
        model = result.scalar_one()
        return self._to_run(model)

    async def list_for_session(
        self,
        session_id: UUID,
        *,
        org_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvaluationRun]:
        stmt = (
            select(EvaluationRunModel)
            .where(EvaluationRunModel.session_id == session_id)
            .options(selectinload(EvaluationRunModel.metrics))
            .order_by(EvaluationRunModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if org_id is not None:
            stmt = stmt.where(EvaluationRunModel.org_id == org_id)
        result = await self._session.execute(stmt)
        return [self._to_run(m) for m in result.scalars()]

    @staticmethod
    def _to_run(model: EvaluationRunModel) -> EvaluationRun:
        return EvaluationRun(
            id=model.id,
            org_id=model.org_id,
            session_id=model.session_id,
            user_transcript=model.user_transcript,
            assistant_response=model.assistant_response,
            overall_score=model.overall_score,
            overall_status=EvaluationStatus(model.overall_status),
            metrics=[
                EvaluationMetric(
                    name=MetricName(m.name),
                    score=m.score,
                    value=m.value,
                    unit=m.unit,
                    status=EvaluationStatus(m.status),
                    details=m.details or {},
                )
                for m in model.metrics
            ],
            created_at=model.created_at,
        )
