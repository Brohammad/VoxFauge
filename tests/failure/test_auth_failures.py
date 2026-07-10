"""Failure-mode tests: authentication and authorization errors."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.failure


@pytest.mark.asyncio
async def test_invalid_jwt_rejected(auth_client):
    headers = {"Authorization": "Bearer not.a.valid.jwt"}
    response = await auth_client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_rejected(auth_client):
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_replay_token_rejected(auth_client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long")
    from voxforge.config import get_settings

    get_settings.cache_clear()

    session_id = uuid4()
    response = await auth_client.get(
        f"/api/v1/sessions/{session_id}/replay",
        params={"token": "invalid-token.no-match"},
    )
    assert response.status_code in (401, 403, 404)


@pytest.mark.asyncio
async def test_api_key_scope_violation(auth_client):
    register = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": f"scope-{uuid4().hex[:8]}@example.com",
            "password": "securepass123",
            "full_name": "Scope User",
            "org_name": "Scope Org",
        },
    )
    token = register.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    key_resp = await auth_client.post(
        "/api/v1/api-keys",
        json={"name": "metrics-only", "scopes": ["metrics:read"]},
        headers=headers,
    )
    assert key_resp.status_code == 201
    api_key = key_resp.json()["raw_key"]
    key_headers = {"X-API-Key": api_key}

    create = await auth_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "blocked-collection"},
        headers=key_headers,
    )
    assert create.status_code == 403
