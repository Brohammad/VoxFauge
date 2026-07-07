from uuid import uuid4

import pytest

from voxforge.core.domain.entities import SessionPhase, SessionState
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore


@pytest.mark.asyncio
async def test_save_and_get_state(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    session_id = uuid4()
    state = SessionState(session_id=session_id, phase=SessionPhase.LISTENING)
    await store.save_state(state)

    loaded = await store.get_state(session_id)
    assert loaded.session_id == session_id
    assert loaded.phase == SessionPhase.LISTENING


@pytest.mark.asyncio
async def test_get_state_not_found(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    with pytest.raises(SessionNotFoundError):
        await store.get_state(uuid4())


@pytest.mark.asyncio
async def test_update_phase(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    session_id = uuid4()
    state = SessionState(session_id=session_id, phase=SessionPhase.IDLE)
    await store.save_state(state)

    updated = await store.update_phase(session_id, SessionPhase.SPEAKING)
    assert updated.phase == SessionPhase.SPEAKING
    assert updated.sequence == 1


@pytest.mark.asyncio
async def test_set_interrupt(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    session_id = uuid4()
    state = SessionState(session_id=session_id)
    await store.save_state(state)

    updated = await store.set_interrupt(session_id)
    assert updated.interrupt is True


@pytest.mark.asyncio
async def test_record_heartbeat(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    session_id = uuid4()
    state = SessionState(session_id=session_id)
    await store.save_state(state)

    await store.record_heartbeat(session_id)
    assert not await store.is_stale(session_id, stale_timeout_seconds=45)


@pytest.mark.asyncio
async def test_delete_state(fake_redis):
    store = RedisSessionStateStore(fake_redis)
    session_id = uuid4()
    state = SessionState(session_id=session_id)
    await store.save_state(state)

    await store.delete_state(session_id)
    with pytest.raises(SessionNotFoundError):
        await store.get_state(session_id)
