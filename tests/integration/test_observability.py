"""Integration tests for observability hardening (metrics, health, tracing)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from voxforge.config import get_settings
from voxforge.infrastructure.observability.health import KNOWLEDGE_WORKER_HEARTBEAT_KEY
from voxforge.modules.replay.application.service import ReplayService


@pytest.mark.asyncio
async def test_metrics_endpoint_anonymous_in_development(test_client):
    response = await test_client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "voxforge" in response.text


@pytest.mark.asyncio
async def test_metrics_endpoint_requires_auth_in_production(test_client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("METRICS_ALLOW_ANONYMOUS", "false")
    get_settings.cache_clear()
    response = await test_client.get("/api/v1/metrics")
    assert response.status_code == 401
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_metrics_endpoint_accepts_bearer_token(test_client, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("METRICS_ALLOW_ANONYMOUS", "false")
    monkeypatch.setenv("METRICS_BEARER_TOKEN", "prom-scrape-token")
    get_settings.cache_clear()
    response = await test_client.get(
        "/api/v1/metrics",
        headers={"Authorization": "Bearer prom-scrape-token"},
    )
    assert response.status_code == 200
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ready_endpoint_reports_all_checks(test_client):
    response = await test_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
    for key in (
        "livekit",
        "mcp_registry",
        "embedding_provider",
        "llm_provider",
        "knowledge_worker",
    ):
        assert key in data


@pytest.mark.asyncio
async def test_ready_degraded_when_redis_unavailable(test_client, monkeypatch):
    from voxforge.infrastructure import redis as redis_module

    class BrokenRedis:
        async def ping(self):
            raise ConnectionError("redis down")

        async def get(self, *_args, **_kwargs):
            raise ConnectionError("redis down")

    redis_module.client._redis = BrokenRedis()
    response = await test_client.get("/api/v1/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert "error" in data["redis"]


@pytest.mark.asyncio
async def test_ready_degraded_when_knowledge_worker_stale(test_client, fake_redis, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    get_settings.cache_clear()
    response = await test_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert "heartbeat" in data["knowledge_worker"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ready_ok_when_knowledge_worker_heartbeat_fresh(test_client, fake_redis, monkeypatch):
    import time

    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    get_settings.cache_clear()
    await fake_redis.set(KNOWLEDGE_WORKER_HEARTBEAT_KEY, str(time.time()))
    response = await test_client.get("/api/v1/ready")
    data = response.json()
    assert data["knowledge_worker"] == "ok"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_ready_unavailable_when_database_unavailable(test_client, monkeypatch):
    from voxforge.infrastructure import db as db_module

    class BrokenConn:
        async def __aenter__(self):
            raise ConnectionError("db down")

        async def __aexit__(self, *_args):
            return False

    class BrokenEngine:
        def connect(self):
            return BrokenConn()

    db_module.session._engine = BrokenEngine()
    response = await test_client.get("/api/v1/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unavailable"
    assert "error" in data["database"]


@pytest.mark.asyncio
async def test_replay_service_emits_trace_span(db_session):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    from voxforge.infrastructure.db.replay_repository import ReplayRepository

    repo = ReplayRepository(db_session)
    service = ReplayService(repo)

    with patch.object(repo, "get_session_replay", return_value=object()):
        await service.get_session_replay(
            UUID("00000000-0000-0000-0000-000000000001"),
            org_id=UUID("00000000-0000-0000-0000-000000000010"),
        )

    spans = exporter.get_finished_spans()
    assert any(s.name == "replay.get_session" for s in spans)
