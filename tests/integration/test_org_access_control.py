import pytest


@pytest.mark.asyncio
async def test_org_routes_require_bearer_auth(auth_client):
    create = await auth_client.post("/api/v1/orgs", json={"name": "No Auth Org"})
    assert create.status_code == 401

    listed = await auth_client.get("/api/v1/orgs")
    assert listed.status_code == 401
