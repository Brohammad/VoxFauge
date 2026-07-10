from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
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
    ) -> tuple[OutcomeKPIModel, bool]:
        """Upsert outcome KPI for a session. Returns (model, created)."""
        result = await self._session.execute(
            select(OutcomeKPIModel).where(OutcomeKPIModel.session_id == session_id).limit(1)
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(UTC)

        if existing is not None:
            existing.intent = intent
            existing.task_success = task_success
            existing.escalation = escalation
            existing.resolution_time_seconds = resolution_time_seconds
            existing.recorded_at = now
            await self._session.flush()
            await self._session.refresh(existing)
            return existing, False

        values = {
            "org_id": org_id,
            "session_id": session_id,
            "intent": intent,
            "task_success": task_success,
            "escalation": escalation,
            "resolution_time_seconds": resolution_time_seconds,
            "recorded_at": now,
        }
        update_values = {
            "intent": intent,
            "task_success": task_success,
            "escalation": escalation,
            "resolution_time_seconds": resolution_time_seconds,
            "recorded_at": now,
        }

        dialect = self._session.bind.dialect.name if self._session.bind else ""
        if dialect == "postgresql":
            stmt = (
                pg_insert(OutcomeKPIModel)
                .values(values)
                .on_conflict_do_update(
                    constraint="uq_outcome_kpis_session",
                    set_=update_values,
                )
                .returning(OutcomeKPIModel.id)
            )
        else:
            stmt = (
                sqlite_insert(OutcomeKPIModel)
                .values(values)
                .on_conflict_do_update(
                    index_elements=["session_id"],
                    set_=update_values,
                )
                .returning(OutcomeKPIModel.id)
            )

        insert_result = await self._session.execute(stmt)
        row_id = insert_result.scalar_one()
        model = await self._session.get(OutcomeKPIModel, row_id)
        if model is None:
            raise RuntimeError("outcome not found after upsert")
        return model, True
