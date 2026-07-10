"""End-to-end tests simulating production deployment paths."""

import pytest

from voxforge.config import get_settings

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def e2e_stack(monkeypatch, tmp_path):
    monkeypatch.setenv("STT_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_BLOB_PATH", str(tmp_path / "kb"))
    monkeypatch.setenv("HANDOFF_ENABLED", "true")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_deployment_health_ready_metrics(test_client):
    health = await test_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] in ("ok", "degraded")

    ready = await test_client.get("/api/v1/ready")
    assert ready.status_code in (200, 503)

    metrics = await test_client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "voxforge" in metrics.text or "# HELP" in metrics.text


@pytest.mark.asyncio
async def test_full_voice_onboarding_to_dashboard(auth_client):
    """Docker-compose-like path: register → sample call → replay → dashboard."""
    register = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "e2e-deploy@example.com",
            "password": "securepass123",
            "full_name": "E2E Deploy",
            "org_name": "E2E Deploy Org",
        },
    )
    assert register.status_code == 201
    token = register.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sample = await auth_client.post("/api/v1/onboarding/run-sample-call", headers=headers)
    assert sample.status_code == 200
    session_id = sample.json()["test_session_id"]

    replay = await auth_client.get(f"/api/v1/sessions/{session_id}/replay", headers=headers)
    assert replay.status_code == 200

    dashboard = await auth_client.get("/api/v1/dashboard/outcomes", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_sessions"] >= 1
