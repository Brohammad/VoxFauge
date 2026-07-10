"""Integration tests for enterprise human handoff flow."""

from uuid import uuid4

import pytest

from voxforge.config import get_settings


@pytest.fixture(autouse=True)
def enable_handoff(monkeypatch):
    monkeypatch.setenv("HANDOFF_ENABLED", "true")
    monkeypatch.setenv("HANDOFF_AUTO_POLICY", "true")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _auth_headers(auth_client):
    register_resp = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"handoff-{uuid4().hex[:8]}@example.com",
            "password": "securepass123",
            "full_name": "Handoff Tester",
            "org_name": "Handoff Org",
        },
    )
    assert register_resp.status_code == 201
    token = register_resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_handoff_creates_ticket_summary_and_replay_link(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={
            "trigger": "user_request",
            "reason": "Customer requested human agent",
            "priority": "high",
        },
        headers=headers,
    )
    assert handoff_resp.status_code == 201
    body = handoff_resp.json()
    assert body["ticket_id"] is not None
    assert body["conversation_summary"]
    assert body["replay_url"]
    assert body["status"] in ("pending", "assigned")


@pytest.mark.asyncio
async def test_handoff_idempotent_per_session(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]

    first = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "first"},
        headers=headers,
    )
    second = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "second"},
        headers=headers,
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_conversation_state_survives_handoff(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "policy", "reason": "test snapshot"},
        headers=headers,
    )
    assert handoff_resp.status_code == 201

    session_get = await auth_client.get(f"/api/v1/sessions/{session_id}", headers=headers)
    assert session_get.status_code == 200
    assert session_get.json()["status"] in ("handoff_pending", "created", "active")


@pytest.mark.asyncio
async def test_human_agent_accepts_and_resumes(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "accept test"},
        headers=headers,
    )
    handoff_id = handoff_resp.json()["id"]

    accept_resp = await auth_client.post(
        f"/api/v1/handoffs/{handoff_id}/accept",
        headers=headers,
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_handoff_context_includes_messages_and_ticket(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "context test"},
        headers=headers,
    )
    handoff_id = handoff_resp.json()["id"]

    ctx_resp = await auth_client.get(f"/api/v1/handoffs/{handoff_id}/context", headers=headers)
    assert ctx_resp.status_code == 200
    body = ctx_resp.json()
    assert "conversation_summary" in body
    assert "replay_url" in body
    assert "recent_messages" in body
    assert "ticket" in body


@pytest.mark.asyncio
async def test_handoff_complete_restores_session(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "complete test"},
        headers=headers,
    )
    handoff_id = handoff_resp.json()["id"]
    await auth_client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=headers)

    complete_resp = await auth_client.post(
        f"/api/v1/handoffs/{handoff_id}/complete",
        json={"resolution": "resolved"},
        headers=headers,
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_org_isolation_on_handoff_access(auth_client):
    headers_a = await _auth_headers(auth_client)
    headers_b = await _auth_headers(auth_client)

    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers_a)
    session_id = session_resp.json()["session_id"]
    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "isolation"},
        headers=headers_a,
    )
    handoff_id = handoff_resp.json()["id"]

    resp = await auth_client.get(f"/api/v1/handoffs/{handoff_id}", headers=headers_b)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_replay_timeline_includes_handoff_events(auth_client):
    headers = await _auth_headers(auth_client)
    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    session_id = session_resp.json()["session_id"]
    await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "replay test"},
        headers=headers,
    )

    replay_resp = await auth_client.get(f"/api/v1/sessions/{session_id}/replay", headers=headers)
    assert replay_resp.status_code == 200
    event_types = {e["event_type"] for e in replay_resp.json()["events"]}
    assert "handoff" in event_types
