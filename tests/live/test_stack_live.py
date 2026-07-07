"""Live full-stack tests — require Docker (Postgres + Redis) and API keys.

Run with:
    docker compose up -d postgres redis
    alembic upgrade head
    OPENAI_API_KEY=... pytest -m live tests/live/test_stack_live.py -v
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.live


def _require_stack_env() -> None:
    for name in ("OPENAI_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY"):
        if not os.environ.get(name, "").strip():
            pytest.skip(f"{name} not set — skipping stack live test")


@pytest.mark.asyncio
async def test_health_and_ready() -> None:
    _require_stack_env()

    from voxforge.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        ready = await client.get("/api/v1/ready")
        assert ready.status_code == 200
        body = ready.json()
        assert body["database"] == "ok", body
        assert body["redis"] == "ok", body


@pytest.mark.asyncio
async def test_auth_register_login_flow() -> None:
    _require_stack_env()

    from voxforge.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"live-test-{os.getpid()}@voxforge.test"
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "LiveTestPass123!", "name": "Live Tester"},
        )
        assert register.status_code == 201, register.text
        data = register.json()
        assert "access_token" in data

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "LiveTestPass123!"},
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        sessions = await client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert sessions.status_code == 200
        assert isinstance(sessions.json(), list)
