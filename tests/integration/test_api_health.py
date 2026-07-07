import pytest


@pytest.mark.asyncio
async def test_health_endpoint(test_client):
    response = await test_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint(test_client):
    response = await test_client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "voxforge" in response.text


@pytest.mark.asyncio
async def test_ready_endpoint(test_client):
    response = await test_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "ok"
    assert data["redis"] == "ok"
