from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.tools import ToolCallRecord, ToolCallStatus
from voxforge.infrastructure.db.models import ToolCallModel


class ToolCallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_call(
        self,
        *,
        org_id: UUID | None,
        session_id: UUID | None,
        tool_name: str,
        arguments: dict,
        result: str | None,
        status: ToolCallStatus,
        latency_ms: float | None,
        error: str | None,
    ) -> ToolCallRecord:
        model = ToolCallModel(
            id=uuid4(),
            org_id=org_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            status=status.value,
            latency_ms=latency_ms,
            error=error,
        )
        self._session.add(model)
        await self._session.flush()
        return self._to_entity(model)

    async def list_for_session(
        self,
        session_id: UUID,
        *,
        org_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToolCallRecord]:
        stmt = (
            select(ToolCallModel)
            .where(ToolCallModel.session_id == session_id)
            .order_by(ToolCallModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if org_id is not None:
            stmt = stmt.where(ToolCallModel.org_id == org_id)
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars()]

    @staticmethod
    def _to_entity(model: ToolCallModel) -> ToolCallRecord:
        return ToolCallRecord(
            id=model.id,
            org_id=model.org_id,
            session_id=model.session_id,
            tool_name=model.tool_name,
            arguments=model.arguments,
            result=model.result,
            status=ToolCallStatus(model.status),
            latency_ms=model.latency_ms,
            error=model.error,
            created_at=model.created_at,
        )
