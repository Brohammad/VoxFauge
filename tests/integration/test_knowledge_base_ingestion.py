"""Integration tests for knowledge base ingestion pipeline."""

import io

import pytest

from voxforge.config import get_settings

pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def enable_knowledge(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_BLOB_PATH", str(tmp_path / "kb"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_upload_creates_document_and_processes_inline(test_client):
    coll = await test_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "test-collection"},
    )
    assert coll.status_code == 201
    collection_id = coll.json()["id"]

    content = b"# Handbook\n\nWelcome to the team."
    upload = await test_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": ("handbook.md", io.BytesIO(content), "text/markdown")},
        data={"title": "Employee Handbook"},
    )
    assert upload.status_code == 202
    body = upload.json()
    assert "document_id" in body
    assert "job_id" in body

    doc = await test_client.get(f"/api/v1/knowledge/documents/{body['document_id']}")
    assert doc.status_code == 200
    assert doc.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_ingest_job_reindex(test_client):
    coll = await test_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "reindex-collection"},
    )
    collection_id = coll.json()["id"]
    content = b"Original content for reindex test."
    upload = await test_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": ("doc.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Reindex Doc"},
    )
    document_id = upload.json()["document_id"]

    reindex = await test_client.post(f"/api/v1/knowledge/documents/{document_id}/reindex")
    assert reindex.status_code in (200, 202)
    doc = await test_client.get(f"/api/v1/knowledge/documents/{document_id}")
    assert doc.json()["status"] == "ready"
