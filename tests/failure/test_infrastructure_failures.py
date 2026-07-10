"""Failure-mode tests: infrastructure unavailability and recovery."""

import pytest

from voxforge.config import get_settings
from voxforge.infrastructure.observability.health import run_readiness_checks

pytestmark = pytest.mark.failure


@pytest.mark.asyncio
async def test_readiness_degraded_when_redis_unavailable(monkeypatch):
    async def fail_redis():
        raise ConnectionError("redis down")

    monkeypatch.setattr(
        "voxforge.infrastructure.observability.health._check_redis",
        fail_redis,
    )
    report = await run_readiness_checks(get_settings())
    assert report.status == "unavailable"
    assert "redis" in report.checks


@pytest.mark.asyncio
async def test_readiness_unavailable_when_database_unavailable(monkeypatch):
    async def fail_db():
        raise ConnectionError("postgres down")

    monkeypatch.setattr(
        "voxforge.infrastructure.observability.health._check_database",
        fail_db,
    )
    report = await run_readiness_checks(get_settings())
    assert report.status == "unavailable"
    assert report.http_status == 503


@pytest.mark.asyncio
async def test_rate_limit_fail_open_for_health_when_redis_unavailable(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_FAIL_CLOSED_CATEGORIES", "auth_login")
    get_settings.cache_clear()

    class BrokenRedis:
        async def incr(self, _key):
            raise ConnectionError("redis unavailable")

        async def expire(self, _key, _ttl):
            raise ConnectionError("redis unavailable")

    import voxforge.infrastructure.http.rate_limit as rl_module

    original = rl_module.get_redis
    rl_module.get_redis = lambda: BrokenRedis()
    try:
        from voxforge.config import Settings
        from voxforge.infrastructure.http.rate_limit import RateLimiter, get_policy_by_category

        limiter = RateLimiter(Settings())
        result = await limiter.check_ip(
            get_policy_by_category("dashboard"),
            "203.0.113.10",
            "/api/v1/dashboard/outcomes",
        )
        assert result.allowed
        assert result.redis_error
    finally:
        rl_module.get_redis = original
        get_settings.cache_clear()
