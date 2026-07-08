import pytest


async def _auth_headers(client, email: str):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Config User",
            "org_name": "Config Org",
        },
    )
    assert response.status_code == 201
    token = response.json()["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_agent_config_create_list_and_rollback(auth_client):
    headers = await _auth_headers(auth_client, "configs@example.com")

    create_v1 = await auth_client.post(
        "/api/v1/agent-configs",
        headers=headers,
        json={
            "label": "baseline",
            "prompt_config": {"system_prompt": "Be concise and helpful."},
            "orchestrator_config": {"mode": "single"},
            "eval_thresholds": {"task_success_min": 0.8},
            "change_note": "initial",
            "activate": True,
        },
    )
    assert create_v1.status_code == 201
    v1 = create_v1.json()
    assert v1["version"] == 1
    assert v1["is_active"] is True

    create_v2 = await auth_client.post(
        "/api/v1/agent-configs",
        headers=headers,
        json={
            "label": "experimental",
            "prompt_config": {"system_prompt": "Be experimental."},
            "orchestrator_config": {"mode": "multi_agent"},
            "eval_thresholds": {"task_success_min": 0.9},
            "change_note": "try multi-agent",
            "activate": True,
        },
    )
    assert create_v2.status_code == 201
    v2 = create_v2.json()
    assert v2["version"] == 2
    assert v2["is_active"] is True

    listed = await auth_client.get("/api/v1/agent-configs", headers=headers)
    assert listed.status_code == 200
    versions = listed.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert sum(1 for item in versions if item["is_active"]) == 1

    active = await auth_client.get("/api/v1/agent-configs/active", headers=headers)
    assert active.status_code == 200
    assert active.json()["version"] == 2
    assert active.json()["prompt_config"]["system_prompt"] == "Be experimental."

    rollback = await auth_client.post(
        "/api/v1/agent-configs/rollback",
        headers=headers,
        json={"target_version": 1, "change_note": "rollback after regression"},
    )
    assert rollback.status_code == 200
    rolled = rollback.json()
    assert rolled["version"] == 3
    assert rolled["is_active"] is True
    assert rolled["prompt_config"]["system_prompt"] == "Be concise and helpful."
    assert rolled["label"] == "rollback-from-v1"

    active_after = await auth_client.get("/api/v1/agent-configs/active", headers=headers)
    assert active_after.status_code == 200
    assert active_after.json()["version"] == 3
