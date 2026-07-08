import pytest


async def _register_and_token(client, email: str):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Onboarding User",
            "org_name": "Onboarding Org",
        },
    )
    assert response.status_code == 201
    return response.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_onboarding_and_template_endpoints(auth_client):
    token = await _register_and_token(auth_client, "onboarding@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    template_resp = await auth_client.get("/api/v1/templates/support/default", headers=headers)
    assert template_resp.status_code == 200
    assert template_resp.json()["slug"] == "customer-support-deflection"

    start_resp = await auth_client.post("/api/v1/onboarding/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "started"

    connect_resp = await auth_client.post(
        "/api/v1/onboarding/connect-token",
        json={"token_preview": "abcdef12"},
        headers=headers,
    )
    assert connect_resp.status_code == 200
    assert connect_resp.json()["status"] == "token_connected"

    sample_resp = await auth_client.post("/api/v1/onboarding/run-sample-call", headers=headers)
    assert sample_resp.status_code == 200
    assert sample_resp.json()["status"] == "test_call_passed"
    assert sample_resp.json()["test_session_id"] is not None

    status_resp = await auth_client.get("/api/v1/onboarding/status", headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "test_call_passed"

    outcomes_resp = await auth_client.get("/api/v1/dashboard/outcomes", headers=headers)
    assert outcomes_resp.status_code == 200
    outcomes = outcomes_resp.json()
    assert outcomes["total_sessions"] == 1
    assert outcomes["task_success_rate"] == 1.0
    assert outcomes["escalation_rate"] == 0.0
    assert "billing_contact_change" in outcomes["top_intents"]
    assert len(outcomes["trend"]) == 1
