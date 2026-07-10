import json
from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as aioredis

from voxforge.core.domain.entities import SessionPhase, SessionState
from voxforge.core.exceptions import SessionNotFoundError


class RedisSessionStateStore:
    def __init__(self, redis_client: aioredis.Redis, ttl_seconds: int = 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _state_key(self, session_id: UUID) -> str:
        return f"session:{session_id}:state"

    def _heartbeat_key(self, session_id: UUID) -> str:
        return f"session:{session_id}:heartbeat"

    async def save_state(self, state: SessionState, *, ttl_seconds: int | None = None) -> None:
        key = self._state_key(state.session_id)
        data = state.model_dump(mode="json")
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl
        await self._redis.set(key, json.dumps(data), ex=ttl)

    async def get_state(self, session_id: UUID) -> SessionState:
        key = self._state_key(session_id)
        raw = await self._redis.get(key)
        if raw is None:
            raise SessionNotFoundError(str(session_id))
        data = json.loads(raw)
        return SessionState.model_validate(data)

    async def get_state_or_none(self, session_id: UUID) -> SessionState | None:
        try:
            return await self.get_state(session_id)
        except SessionNotFoundError:
            return None

    async def update_phase(self, session_id: UUID, phase: SessionPhase) -> SessionState:
        state = await self.get_state(session_id)
        state.phase = phase
        state.sequence += 1
        await self.save_state(state)
        return state

    async def set_interrupt(self, session_id: UUID, value: bool = True) -> SessionState:
        state = await self.get_state(session_id)
        state.interrupt = value
        state.sequence += 1
        await self.save_state(state)
        return state

    async def clear_interrupt(self, session_id: UUID) -> SessionState:
        return await self.set_interrupt(session_id, False)

    async def record_heartbeat(self, session_id: UUID) -> None:
        key = self._heartbeat_key(session_id)
        now = datetime.now(UTC).isoformat()
        await self._redis.set(key, now, ex=self._ttl)
        state = await self.get_state(session_id)
        state.last_heartbeat = datetime.now(UTC)
        await self.save_state(state)

    async def is_stale(self, session_id: UUID, stale_timeout_seconds: int) -> bool:
        key = self._heartbeat_key(session_id)
        raw = await self._redis.get(key)
        if raw is None:
            return True
        last = datetime.fromisoformat(raw)
        elapsed = (datetime.now(UTC) - last).total_seconds()
        return elapsed > stale_timeout_seconds

    async def delete_state(self, session_id: UUID) -> None:
        await self._redis.delete(self._state_key(session_id), self._heartbeat_key(session_id))
