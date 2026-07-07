import pytest

from voxforge.core.domain.entities import MessageRole, SessionStatus, TransportType
from voxforge.core.events.bus import EventBus
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.session_manager.application.service import SessionManager


@pytest.fixture
def settings():
    from voxforge.config import Settings

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


@pytest.mark.asyncio
async def test_create_session(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    bus = EventBus()
    manager = SessionManager(db_session, store, bus, settings)

    session = await manager.create_session(config={"language": "en"})
    await db_session.commit()

    assert session.status == SessionStatus.CREATED
    assert session.transport_type == TransportType.WEBSOCKET

    state = await store.get_state(session.id)
    assert state.config == {"language": "en"}


@pytest.mark.asyncio
async def test_activate_session(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    bus = EventBus()
    manager = SessionManager(db_session, store, bus, settings)

    session = await manager.create_session()
    activated = await manager.activate_session(session.id)
    await db_session.commit()

    assert activated.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_save_messages(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    bus = EventBus()
    manager = SessionManager(db_session, store, bus, settings)

    session = await manager.create_session()
    await manager.save_user_message(session.id, "Hello")
    await manager.save_assistant_message(session.id, "Hi there!")
    await db_session.commit()

    messages = await manager.get_messages(session.id)
    assert len(messages) == 2
    assert messages[0].role == MessageRole.USER
    assert messages[1].role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_end_session(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    bus = EventBus()
    manager = SessionManager(db_session, store, bus, settings)

    session = await manager.create_session()
    ended = await manager.end_session(session.id)
    await db_session.commit()

    assert ended.status == SessionStatus.COMPLETED
    assert ended.ended_at is not None

    with pytest.raises(SessionNotFoundError):
        await store.get_state(session.id)
