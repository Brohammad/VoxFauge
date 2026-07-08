import pytest


async def _register(auth_client, email: str):
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": "Audit User",
            "org_name": "Audit Org",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["tokens"]["access_token"], body["org_id"]


@pytest.mark.asyncio
async def test_audit_log_list_and_export(auth_client):
    token, org_id = await _register(auth_client, "audit-export@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_org = await auth_client.post(
        "/api/v1/orgs",
        json={"name": "Another Org"},
        headers=headers,
    )
    assert create_org.status_code == 201

    logs = await auth_client.get(f"/api/v1/orgs/{org_id}/audit-logs", headers=headers)
    assert logs.status_code == 200
    payload = logs.json()
    assert len(payload) >= 1
    assert any(item["action"] == "user.registered" for item in payload)

    export_csv = await auth_client.get(
        f"/api/v1/orgs/{org_id}/audit-logs/export?format=csv",
        headers=headers,
    )
    assert export_csv.status_code == 200
    assert export_csv.headers["content-type"].startswith("text/csv")
    assert "action" in export_csv.text

    export_json = await auth_client.get(
        f"/api/v1/orgs/{org_id}/audit-logs/export?format=json",
        headers=headers,
    )
    assert export_json.status_code == 200
    assert export_json.headers["content-type"].startswith("application/json")
    json_body = export_json.json()
    assert isinstance(json_body, list)
    assert any(item["action"] == "user.registered" for item in json_body)
