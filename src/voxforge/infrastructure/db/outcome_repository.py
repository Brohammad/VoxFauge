from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.infrastructure.db.models import OutcomeKPIModel


class OutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_session_outcome(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        intent: str,
        task_success: bool,
        escalation: bool,
        resolution_time_seconds: float,
    ) -> OutcomeKPIModel:
        result = await self._session.execute(
            select(OutcomeKPIModel).where(OutcomeKPIModel.session_id == session_id).limit(1)
        )
        model = result.scalar_one_or_none()

        if model is None:
            model = OutcomeKPIModel(
                org_id=org_id,
                session_id=session_id,
                intent=intent,
                task_success=task_success,
                escalation=escalation,
                resolution_time_seconds=resolution_time_seconds,
                recorded_at=datetime.now(UTC),
            )
            self._session.add(model)
        else:
            model.intent = intent
            model.task_success = task_success
            model.escalation = escalation
            model.resolution_time_seconds = resolution_time_seconds
            model.recorded_at = datetime.now(UTC)

        await self._session.flush()
        await self._session.refresh(model)
        return model
