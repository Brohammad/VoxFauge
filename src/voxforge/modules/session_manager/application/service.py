from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings
from voxforge.core.domain.entities import (
    MessageRole,
    SessionPhase,
    SessionState,
    SessionStatus,
    TransportType,
    TurnMetrics,
    VoiceSession,
)
from voxforge.core.domain.events import SessionCreated, SessionEnded, SessionResumed
from voxforge.core.events.bus import EventBus
from voxforge.infrastructure.db.repositories import SessionRepository
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore


class SessionManager:
    def __init__(
        self,
        db_session: AsyncSession,
        state_store: RedisSessionStateStore,
        event_bus: EventBus,
        settings: Settings,
    ) -> None:
        self._repo = SessionRepository(db_session)
        self._state_store = state_store
        self._event_bus = event_bus
        self._settings = settings
        self._db_session = db_session

    async def create_session(
        self,
        *,
        transport_type: TransportType = TransportType.WEBSOCKET,
        config: dict | None = None,
        org_id: UUID | None = None,
        created_by_user_id: UUID | None = None,
    ) -> VoiceSession:
        session = await self._repo.create(
            transport_type=transport_type,
            metadata=config or {},
            org_id=org_id,
            created_by_user_id=created_by_user_id,
        )
        state = SessionState(session_id=session.id, config=config or {})
        await self._state_store.save_state(state)
        await self._state_store.record_heartbeat(session.id)
        await self._event_bus.publish(SessionCreated(session_id=session.id))
        return session

    async def activate_session(self, session_id: UUID) -> VoiceSession:
        session = await self._repo.update_status(session_id, SessionStatus.ACTIVE)
        await self._state_store.update_phase(session_id, SessionPhase.LISTENING)
        return session

    async def resume_session(self, session_id: UUID, last_sequence: int = 0) -> VoiceSession:
        session = await self._repo.get(session_id)
        state = await self._state_store.get_state(session_id)
        if state.sequence < last_sequence:
            state.sequence = last_sequence
            await self._state_store.save_state(state)
        await self._state_store.record_heartbeat(session_id)
        await self._event_bus.publish(
            SessionResumed(session_id=session_id, last_sequence=last_sequence)
        )
        return session

    async def end_session(
        self, session_id: UUID, *, reason: str = "normal"
    ) -> VoiceSession:
        session = await self._repo.end_session(session_id)
        await self._state_store.delete_state(session_id)
        await self._event_bus.publish(SessionEnded(session_id=session_id, reason=reason))
        return session

    async def save_user_message(self, session_id: UUID, content: str, metadata: dict | None = None):
        return await self._repo.add_message(
            session_id,
            role=MessageRole.USER,
            content=content,
            provider_metadata=metadata or {},
        )

    async def save_assistant_message(
        self, session_id: UUID, content: str, metadata: dict | None = None
    ):
        return await self._repo.add_message(
            session_id,
            role=MessageRole.ASSISTANT,
            content=content,
            provider_metadata=metadata or {},
        )

    async def save_system_message(self, session_id: UUID, content: str):
        return await self._repo.add_message(
            session_id,
            role=MessageRole.SYSTEM,
            content=content,
        )

    async def get_messages(self, session_id: UUID, offset: int = 0, limit: int = 50):
        return await self._repo.get_messages(session_id, offset=offset, limit=limit)

    async def save_turn_metrics(self, session_id: UUID, metrics: TurnMetrics) -> None:
        if metrics.stt_ms is not None:
            await self._repo.add_metric(session_id, metric_name="stt_ms", value_ms=metrics.stt_ms)
        if metrics.llm_first_token_ms is not None:
            await self._repo.add_metric(
                session_id, metric_name="llm_first_token_ms", value_ms=metrics.llm_first_token_ms
            )
        if metrics.tts_first_byte_ms is not None:
            await self._repo.add_metric(
                session_id, metric_name="tts_first_byte_ms", value_ms=metrics.tts_first_byte_ms
            )
        if metrics.e2e_ms is not None:
            await self._repo.add_metric(session_id, metric_name="e2e_ms", value_ms=metrics.e2e_ms)

    async def get_session(self, session_id: UUID, *, org_id: UUID | None = None) -> VoiceSession:
        return await self._repo.get(session_id, org_id=org_id)

    async def set_interrupt(self, session_id: UUID) -> SessionState:
        return await self._state_store.set_interrupt(session_id, True)

    async def clear_interrupt(self, session_id: UUID) -> SessionState:
        return await self._state_store.clear_interrupt(session_id)

    async def update_phase(self, session_id: UUID, phase: SessionPhase) -> SessionState:
        return await self._state_store.update_phase(session_id, phase)

    async def record_heartbeat(self, session_id: UUID) -> None:
        await self._state_store.record_heartbeat(session_id)

    async def is_stale(self, session_id: UUID) -> bool:
        return await self._state_store.is_stale(
            session_id, self._settings.session_stale_timeout_seconds
        )

    async def get_session_config(self, session_id: UUID) -> dict:
        state = await self._state_store.get_state_or_none(session_id)
        return state.config if state else {}

    async def commit(self) -> None:
        await self._db_session.commit()
