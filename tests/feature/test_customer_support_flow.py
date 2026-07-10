"""Feature test: customer support flow end-to-end."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.feature


async def _register(auth_client, prefix: str) -> dict:
    resp = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{prefix}-{uuid4().hex[:8]}@example.com",
            "password": "securepass123",
            "full_name": "Support Flow User",
            "org_name": "Support Flow Org",
        },
    )
    assert resp.status_code == 201
    token = resp.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_customer_support_voice_to_handoff_flow(auth_client):
    """Voice session → handoff → ticket → replay → dashboard outcomes."""
    headers = await _register(auth_client, "support-flow")

    session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
    assert session_resp.status_code == 201
    session_id = session_resp.json()["session_id"]

    sample = await auth_client.post("/api/v1/onboarding/run-sample-call", headers=headers)
    assert sample.status_code == 200

    handoff_resp = await auth_client.post(
        f"/api/v1/sessions/{session_id}/handoff",
        json={"trigger": "user_request", "reason": "Customer wants human agent"},
        headers=headers,
    )
    assert handoff_resp.status_code == 201
    handoff = handoff_resp.json()
    assert handoff["ticket_id"]
    assert handoff["replay_url"]
    handoff_id = handoff["id"]

    accept = await auth_client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=headers)
    assert accept.status_code == 200

    replay = await auth_client.get(f"/api/v1/sessions/{session_id}/replay", headers=headers)
    assert replay.status_code == 200
    timeline = replay.json()
    assert timeline["session_id"] == session_id

    outcomes = await auth_client.get("/api/v1/dashboard/outcomes", headers=headers)
    assert outcomes.status_code == 200
    assert outcomes.json()["total_sessions"] >= 1

    complete = await auth_client.post(
        f"/api/v1/handoffs/{handoff_id}/complete",
        json={"resolution": "resolved"},
        headers=headers,
    )
    assert complete.status_code == 200
