"""Unit tests for P1 Group 4 observability hardening."""

from __future__ import annotations

import ipaddress
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from fastapi import HTTPException

from voxforge.config import Settings
from voxforge.core.domain.auth import Principal, PrincipalType
from voxforge.infrastructure.observability.health import HealthReport, _aggregate_status
from voxforge.infrastructure.observability.metrics_auth import (
    METRICS_SCOPE,
    _ip_allowed,
    require_metrics_access,
)
from voxforge.infrastructure.observability.sanitization import _sanitize_string
from voxforge.infrastructure.security.production import collect_production_errors


def test_metrics_scope_constant():
    assert METRICS_SCOPE == "metrics:read"


def test_ip_allowed_single_and_cidr():
    assert _ip_allowed("10.0.0.5", ("10.0.0.5",))
    assert _ip_allowed("10.0.0.5", ("10.0.0.0/8",))
    assert not _ip_allowed("192.168.1.1", ("10.0.0.0/8",))


def test_aggregate_status_unavailable_when_database_down():
    status, code = _aggregate_status({"database": "error: conn", "redis": "ok"})
    assert status == "unavailable"
    assert code == 503


def test_aggregate_status_degraded_when_knowledge_worker_stale():
    status, code = _aggregate_status(
        {"database": "ok", "redis": "ok", "knowledge_worker": "error: heartbeat stale"}
    )
    assert status == "degraded"
    assert code == 200


def test_aggregate_status_ok_when_optional_disabled():
    status, code = _aggregate_status(
        {
            "database": "ok",
            "redis": "ok",
            "livekit": "disabled",
            "mcp_registry": "disabled",
            "embedding_provider": "configured",
            "llm_provider": "configured",
            "knowledge_worker": "disabled",
        }
    )
    assert status == "ok"
    assert code == 200


def test_health_report_to_dict():
    report = HealthReport(status="degraded", checks={"redis": "ok"}, http_status=200)
    assert report.to_dict() == {"status": "degraded", "redis": "ok"}


def test_sanitize_jwt_and_api_key():
    jwt = (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    api_key = "vxf_" + "a" * 32
    raw = f"Authorization: Bearer {jwt} key={api_key}"
    sanitized = _sanitize_string(raw)
    assert jwt not in sanitized
    assert api_key not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_password_field():
    assert "password=[REDACTED]" in _sanitize_string("password=hunter2")


def test_production_rejects_anonymous_metrics():
    settings = Settings(
        app_env="production",
        auth_required=True,
        jwt_secret_key="a" * 32,
        api_key_hash_pepper="b" * 32,
        trusted_hosts="demo.example.com",
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
        handoff_enabled=False,
        metrics_allow_anonymous=True,
    )
    errors = collect_production_errors(settings)
    assert any("METRICS_ALLOW_ANONYMOUS" in e for e in errors)


@pytest.mark.asyncio
async def test_metrics_auth_allows_anonymous_in_development():
    settings = Settings(app_env="development", metrics_allow_anonymous=None)
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock(host="127.0.0.1")
    await require_metrics_access(request, None, None, settings, AsyncMock())


@pytest.mark.asyncio
async def test_metrics_auth_allows_bearer_token():
    settings = Settings(
        app_env="production",
        metrics_allow_anonymous=False,
        metrics_bearer_token="scrape-secret",
    )
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock(host="203.0.113.1")
    from fastapi.security import HTTPAuthorizationCredentials

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="scrape-secret")
    await require_metrics_access(request, creds, None, settings, AsyncMock())


@pytest.mark.asyncio
async def test_metrics_auth_allows_api_key_with_scope():
    settings = Settings(app_env="production", metrics_allow_anonymous=False)
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock(host="203.0.113.1")
    auth_service = AsyncMock()
    auth_service.resolve_principal_from_api_key.return_value = Principal(
        type=PrincipalType.API_KEY,
        org_id=UUID("00000000-0000-0000-0000-000000000010"),
        scopes=["metrics:read"],
        api_key_id=UUID("00000000-0000-0000-0000-000000000099"),
    )
    await require_metrics_access(request, None, "vxf_testkey", settings, auth_service)


@pytest.mark.asyncio
async def test_metrics_auth_rejects_unauthenticated():
    settings = Settings(app_env="production", metrics_allow_anonymous=False)
    request = MagicMock()
    request.headers = {}
    request.client = MagicMock(host="203.0.113.1")
    auth_service = AsyncMock()
    auth_service.resolve_principal_from_api_key.side_effect = Exception("invalid")
    with pytest.raises(HTTPException) as exc:
        await require_metrics_access(request, None, None, settings, auth_service)
    assert exc.value.status_code == 401


def test_metrics_allowed_ip_list_parsing():
    settings = Settings(metrics_allowed_ips="10.0.0.0/8, 172.16.0.1")
    assert settings.metrics_allowed_ip_list == ("10.0.0.0/8", "172.16.0.1")
    assert ipaddress.ip_address("10.1.2.3") in ipaddress.ip_network(
        settings.metrics_allowed_ip_list[0]
    )
