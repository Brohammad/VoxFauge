"""Unit and integration tests for P1 Group 3 rate limiting."""

import pytest
from httpx import ASGITransport, AsyncClient

from voxforge.config import Settings
from voxforge.infrastructure.http.rate_limit import (
    RateLimiter,
    get_policy_by_category,
    resolve_policy,
)
from voxforge.main import app


@pytest.fixture
def strict_settings():
    return Settings(
        rate_limit_enabled=True,
        rate_limit_multiplier=1.0,
        rate_limit_fail_closed_categories="auth_login,demo",
        redis_url="redis://localhost:6379/0",
    )


def test_resolve_policy_auth_login():
    policy = resolve_policy("POST", "/api/v1/auth/login")
    assert policy is not None
    assert policy.category == "auth_login"


def test_resolve_policy_exempt_health():
    assert resolve_policy("GET", "/api/v1/health") is None


def test_resolve_policy_knowledge_upload():
    policy = resolve_policy(
        "POST",
        "/api/v1/knowledge/collections/00000000-0000-4000-8000-000000000001/documents",
    )
    assert policy is not None
    assert policy.category == "knowledge_upload"


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_burst(fake_redis, strict_settings):
    import voxforge.infrastructure.http.rate_limit as rl_module

    rl_module.get_redis = lambda: fake_redis
    policy = get_policy_by_category("demo")
    limiter = RateLimiter(strict_settings)
    path = "/api/v1/demo/info"

    for _ in range(policy.burst_per_10_seconds):
        result = await limiter.check_ip(policy, "203.0.113.1", path)
        assert result.allowed

    blocked = await limiter.check_ip(policy, "203.0.113.1", path)
    assert blocked.blocked


@pytest.mark.asyncio
async def test_rate_limiter_fail_closed_on_redis_error(strict_settings):
    import voxforge.infrastructure.http.rate_limit as rl_module

    class BrokenRedis:
        async def incr(self, _key):
            raise ConnectionError("redis down")

        async def expire(self, _key, _ttl):
            raise ConnectionError("redis down")

    original = rl_module.get_redis
    rl_module.get_redis = lambda: BrokenRedis()
    try:
        policy = get_policy_by_category("auth_login")
        limiter = RateLimiter(strict_settings)
        result = await limiter.check_ip(policy, "203.0.113.2", "/api/v1/auth/login")
    finally:
        rl_module.get_redis = original

    assert result.redis_error
    assert not result.allowed


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_for_dashboard(fake_redis, strict_settings):
    settings = strict_settings.model_copy(
        update={"rate_limit_fail_closed_categories": "auth_login"}
    )
    policy = get_policy_by_category("dashboard")
    limiter = RateLimiter(settings)

    class BrokenRedis:
        async def incr(self, _key):
            raise ConnectionError("redis down")

        async def expire(self, _key, _ttl):
            raise ConnectionError("redis down")

    import voxforge.infrastructure.http.rate_limit as rl_module

    original = rl_module.get_redis
    rl_module.get_redis = lambda: BrokenRedis()
    try:
        result = await limiter.check_ip(policy, "203.0.113.3", "/api/v1/dashboard/overview")
    finally:
        rl_module.get_redis = original

    assert result.allowed
    assert result.redis_error


@pytest.mark.asyncio
async def test_middleware_returns_429(test_client, fake_redis, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "0.01")
    from voxforge.config import get_settings

    get_settings.cache_clear()

    # Unique IP to avoid cross-test bucket pollution in shared fake_redis.
    headers = {"X-Forwarded-For": "198.51.100.99"}
    response = None
    for _ in range(5):
        response = await test_client.get("/api/v1/demo/info", headers=headers)
        if response.status_code == 429:
            break

    assert response is not None
    assert response.status_code == 429
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_auth_login_fail_closed_when_redis_unavailable(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED_CATEGORIES", "auth_login")
    from voxforge.config import get_settings

    get_settings.cache_clear()

    import voxforge.infrastructure.http.rate_limit as rl_module

    class BrokenRedis:
        async def incr(self, _key):
            raise ConnectionError("redis down")

        async def expire(self, _key, _ttl):
            raise ConnectionError("redis down")

    original_get_redis = rl_module.get_redis

    def broken_get_redis():
        return BrokenRedis()

    rl_module.get_redis = broken_get_redis

    from voxforge.infrastructure import redis as redis_module

    redis_module.client._redis = None

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "wrong"},
            )
    finally:
        rl_module.get_redis = original_get_redis
        get_settings.cache_clear()

    assert response.status_code == 503
