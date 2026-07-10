"""Integration tests for rate limiting on expensive endpoints."""

from uuid import uuid4

import pytest

from voxforge.config import get_settings


@pytest.fixture(autouse=True)
def enable_rate_limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "0.05")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _auth_headers(auth_client):
    client_ip = f"203.0.113.{uuid4().int % 200 + 1}"
    register_resp = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rl-{uuid4().hex[:8]}@example.com",
            "password": "securepass123",
            "full_name": "Rate Limit Tester",
            "org_name": "RL Org",
        },
        headers={"X-Forwarded-For": client_ip},
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Forwarded-For": client_ip}


@pytest.mark.asyncio
async def test_session_create_throttled(auth_client):
    headers = await _auth_headers(auth_client)
    blocked = False
    for _ in range(8):
        response = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
        if response.status_code == 429:
            blocked = True
            break
    assert blocked


@pytest.mark.asyncio
async def test_replay_throttled(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]

    blocked = False
    for _ in range(15):
        response = await auth_client.get(
            f"/api/v1/sessions/{session_id}/replay",
            headers=headers,
        )
        if response.status_code == 429:
            blocked = True
            break
    assert blocked
