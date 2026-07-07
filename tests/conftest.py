from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from voxforge.api.dependencies import get_current_principal
from voxforge.config import get_settings
from voxforge.core.domain.auth import OrgRole, Principal, PrincipalType
from voxforge.infrastructure.db.base import Base
from voxforge.main import app

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
TEST_ORG_ID = UUID("00000000-0000-0000-0000-000000000010")


async def _test_principal() -> Principal:
    return Principal(
        type=PrincipalType.USER,
        user_id=TEST_USER_ID,
        org_id=TEST_ORG_ID,
        role=OrgRole.OWNER,
    )


@pytest.fixture(autouse=True)
def auth_disabled(request):
    if "auth_client" in request.fixturenames:
        yield
        return

    app.dependency_overrides[get_current_principal] = _test_principal
    get_settings.cache_clear()
    yield
    app.dependency_overrides.pop(get_current_principal, None)
    get_settings.cache_clear()


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


@pytest_asyncio.fixture
async def auth_client(fake_redis, db_engine, monkeypatch):
    from voxforge.infrastructure import db as db_module
    from voxforge.infrastructure import redis as redis_module

    app.dependency_overrides.pop(get_current_principal, None)
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
    monkeypatch.setenv("API_KEY_HASH_PEPPER", "test-pepper")
    get_settings.cache_clear()

    db_module.session._engine = db_engine
    db_module.session._session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    redis_module.client._redis = fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    db_module.session._engine = None
    db_module.session._session_factory = None
    redis_module.client._redis = None
    get_settings.cache_clear()
