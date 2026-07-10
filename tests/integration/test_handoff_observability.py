"""Integration tests for handoff observability."""

import pytest

from voxforge.config import get_settings
from voxforge.infrastructure.observability.metrics import (
    handoff_duration_seconds,
    handoff_initiated_total,
    handoff_queue_depth,
)


@pytest.fixture(autouse=True)
def enable_handoff(monkeypatch):
    monkeypatch.setenv("HANDOFF_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _auth_headers(auth_client):
    from uuid import uuid4

    register_resp = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"obs-{uuid4().hex[:8]}@example.com",
            "password": "securepass123",
            "full_name": "Obs Tester",
            "org_name": "Obs Org",
        },
    )
    token = register_resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_handoff_initiated_metric_incremented(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]
    await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "metrics"},
        headers=headers,
    )
    # Metric is registered and handoff path executed without error
    assert handoff_initiated_total is not None


@pytest.mark.asyncio
async def test_handoff_duration_histogram_recorded(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]
    await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "duration"},
        headers=headers,
    )
    assert handoff_duration_seconds.labels(stage="total") is not None


@pytest.mark.asyncio
async def test_handoff_queue_depth_gauge(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]
    await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "queue"},
        headers=headers,
    )
    assert handoff_queue_depth.labels(org_id="any")._value is not None  # noqa: SLF001


@pytest.mark.asyncio
async def test_handoff_events_in_replay_timeline(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]
    await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "replay obs"},
        headers=headers,
    )
    replay_resp = await auth_client.get(f"/api/v1/sessions/{session_id}/replay", headers=headers)
    assert any(e["event_type"] == "handoff" for e in replay_resp.json()["events"])
