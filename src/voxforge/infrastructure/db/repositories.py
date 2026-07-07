from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.entities import (
    Message,
    MessageRole,
    SessionMetric,
    SessionStatus,
    TransportType,
    VoiceSession,
)
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.db.models import MessageModel, SessionMetricModel, VoiceSessionModel


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        transport_type: TransportType = TransportType.WEBSOCKET,
        metadata: dict | None = None,
    ) -> VoiceSession:
        model = VoiceSessionModel(
            status=SessionStatus.CREATED,
            transport_type=transport_type,
            metadata_=metadata or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get(self, session_id: UUID) -> VoiceSession:
        model = await self._session.get(VoiceSessionModel, session_id)
        if model is None:
            raise SessionNotFoundError(str(session_id))
        return self._to_entity(model)

    async def update_status(self, session_id: UUID, status: SessionStatus) -> VoiceSession:
        model = await self._session.get(VoiceSessionModel, session_id)
        if model is None:
            raise SessionNotFoundError(str(session_id))
        model.status = status
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def end_session(
        self, session_id: UUID, *, status: SessionStatus = SessionStatus.COMPLETED
    ) -> VoiceSession:
        from datetime import UTC, datetime

        model = await self._session.get(VoiceSessionModel, session_id)
        if model is None:
            raise SessionNotFoundError(str(session_id))
        model.status = status
        model.ended_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def add_message(
        self,
        session_id: UUID,
        *,
        role: MessageRole,
        content: str,
        content_type: str = "text",
        provider_metadata: dict | None = None,
    ) -> Message:
        model = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            content_type=content_type,
            provider_metadata=provider_metadata or {},
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._message_to_entity(model)

    async def get_messages(
        self, session_id: UUID, *, offset: int = 0, limit: int = 50
    ) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._message_to_entity(m) for m in result.scalars().all()]

    async def add_metric(
        self, session_id: UUID, *, metric_name: str, value_ms: float
    ) -> SessionMetric:
        model = SessionMetricModel(
            session_id=session_id,
            metric_name=metric_name,
            value_ms=value_ms,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._metric_to_entity(model)

    @staticmethod
    def _to_entity(model: VoiceSessionModel) -> VoiceSession:
        return VoiceSession(
            id=model.id,
            status=SessionStatus(model.status),
            transport_type=TransportType(model.transport_type),
            metadata=model.metadata_,
            started_at=model.started_at,
            ended_at=model.ended_at,
            total_latency_ms=model.total_latency_ms,
        )

    @staticmethod
    def _message_to_entity(model: MessageModel) -> Message:
        return Message(
            id=model.id,
            session_id=model.session_id,
            role=MessageRole(model.role),
            content=model.content,
            content_type=model.content_type,
            provider_metadata=model.provider_metadata,
            created_at=model.created_at,
        )

    @staticmethod
    def _metric_to_entity(model: SessionMetricModel) -> SessionMetric:
        return SessionMetric(
            id=model.id,
            session_id=model.session_id,
            metric_name=model.metric_name,
            value_ms=model.value_ms,
            recorded_at=model.recorded_at,
        )
