import pytest

from voxforge.modules.agent_config.application.presets import BUILTIN_POLICY_PRESETS


@pytest.mark.asyncio
async def test_list_policy_presets(auth_client):
    headers = await _auth_headers(auth_client, "presets-list@example.com")
    response = await auth_client.get("/api/v1/agent-configs/presets", headers=headers)
    assert response.status_code == 200
    presets = response.json()
    slugs = {item["slug"] for item in presets}
    for builtin in BUILTIN_POLICY_PRESETS:
        assert builtin.slug in slugs


@pytest.mark.asyncio
async def test_apply_policy_preset_creates_active_version(auth_client):
    headers = await _auth_headers(auth_client, "presets-apply@example.com")
    apply_resp = await auth_client.post(
        "/api/v1/agent-configs/presets/strict-compliance/apply",
        headers=headers,
        json={"change_note": "apply strict preset"},
    )
    assert apply_resp.status_code == 201
    applied = apply_resp.json()
    assert applied["label"] == "preset:strict-compliance"
    assert applied["is_active"] is True
    assert applied["prompt_config"]["style"] == "formal, policy-safe, verification-first"

    active = await auth_client.get("/api/v1/agent-configs/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["version"] == applied["version"]


@pytest.mark.asyncio
async def test_apply_unknown_policy_preset_returns_404(auth_client):
    headers = await _auth_headers(auth_client, "presets-missing@example.com")
    response = await auth_client.post(
        "/api/v1/agent-configs/presets/does-not-exist/apply",
        headers=headers,
        json={},
    )
    assert response.status_code == 404


async def _auth_headers(client, email: str):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Preset User",
            "org_name": "Preset Org",
        },
    )
    assert response.status_code == 201
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
