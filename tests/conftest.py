import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from voxforge.infrastructure.db.base import Base
from voxforge.main import app


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def fake_redis():
    import fakeredis.aioredis

    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest_asyncio.fixture
async def test_client(fake_redis, db_engine):
    from voxforge.infrastructure import db as db_module
    from voxforge.infrastructure import redis as redis_module

    db_module.session._engine = db_engine
    db_module.session._session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    redis_module.client._redis = fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    db_module.session._engine = None
    db_module.session._session_factory = None
    redis_module.client._redis = None
