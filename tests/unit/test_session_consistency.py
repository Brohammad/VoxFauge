"""Session Postgres/Redis consistency tests (P1)."""

import pytest

from voxforge.core.domain.entities import SessionState, SessionStatus
from voxforge.core.events.bus import EventBus
from voxforge.core.exceptions import SessionStateError
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.session_manager.application.service import SessionManager


class FailingRedisStore(RedisSessionStateStore):
    def __init__(self, redis_client, *, fail_on: str) -> None:
        super().__init__(redis_client)
        self._fail_on = fail_on

    async def save_state(self, state: SessionState, *, ttl_seconds: int | None = None) -> None:
        if self._fail_on == "save_state":
            raise ConnectionError("redis unavailable")
        await super().save_state(state, ttl_seconds=ttl_seconds)

    async def delete_state(self, session_id) -> None:
        if self._fail_on == "delete_state":
            raise ConnectionError("redis unavailable")
        await super().delete_state(session_id)


@pytest.fixture
def settings():
    from voxforge.config import Settings

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


@pytest.mark.asyncio
async def test_create_session_compensates_when_redis_fails(db_session, fake_redis, settings):
    store = FailingRedisStore(fake_redis, fail_on="save_state")
    manager = SessionManager(db_session, store, EventBus(), settings)

    with pytest.raises(SessionStateError, match="ephemeral state"):
        await manager.create_session(config={"language": "en"})

    await db_session.commit()
    # No session should remain creatable without a second create — verify failed end in DB
    from sqlalchemy import select

    from voxforge.infrastructure.db.models import VoiceSessionModel

    result = await db_session.execute(select(VoiceSessionModel))
    models = result.scalars().all()
    assert len(models) == 1
    assert models[0].status == SessionStatus.FAILED.value


@pytest.mark.asyncio
async def test_end_session_is_idempotent(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session()
    first = await manager.end_session(session.id, reason="normal")
    second = await manager.end_session(session.id, reason="normal")
    await db_session.commit()

    assert first.status == SessionStatus.COMPLETED
    assert second.status == SessionStatus.COMPLETED
    assert first.id == second.id


@pytest.mark.asyncio
async def test_end_session_succeeds_when_redis_delete_fails(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session()
    await db_session.commit()

    failing = FailingRedisStore(fake_redis, fail_on="delete_state")
    manager._state_store = failing  # noqa: SLF001 — test seam

    ended = await manager.end_session(session.id)
    await db_session.commit()

    assert ended.status == SessionStatus.COMPLETED
    # Redis key may remain until TTL; Postgres is authoritative
    state = await store.get_state_or_none(session.id)
    assert state is not None


@pytest.mark.asyncio
async def test_resume_reconciles_missing_redis_state(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session(config={"caller_scopes": ["sessions:write"]})
    await manager.activate_session(session.id)
    await db_session.commit()

    await store.delete_state(session.id)

    resumed = await manager.resume_session(session.id, last_sequence=3)
    state = await store.get_state(session.id)

    assert resumed.status == SessionStatus.ACTIVE
    assert state.sequence == 3
    assert state.config.get("caller_scopes") == ["sessions:write"]


@pytest.mark.asyncio
async def test_get_session_config_falls_back_to_postgres(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session(config={"language": "fr"})
    await db_session.commit()
    await store.delete_state(session.id)

    config = await manager.get_session_config(session.id)
    assert config.get("language") == "fr"


@pytest.mark.asyncio
async def test_ensure_ephemeral_state_rejects_terminal_session(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session()
    await manager.end_session(session.id)
    await db_session.commit()

    with pytest.raises(SessionStateError):
        await manager.ensure_ephemeral_state(session.id)


@pytest.mark.asyncio
async def test_concurrent_end_session_idempotent(db_session, fake_redis, settings):
    import asyncio

    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)
    session = await manager.create_session()
    await db_session.commit()

    results = await asyncio.gather(
        manager.end_session(session.id, reason="a"),
        manager.end_session(session.id, reason="b"),
    )
    await db_session.commit()

    assert all(r.status == SessionStatus.COMPLETED for r in results)
