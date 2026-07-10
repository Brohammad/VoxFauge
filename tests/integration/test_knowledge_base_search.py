"""Integration tests for knowledge base semantic search (mock embeddings)."""

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


async def _seed_collection(test_client, title: str, content: bytes):
    coll = await test_client.post(
        "/api/v1/knowledge/collections",
        json={"name": f"coll-{title}"},
    )
    collection_id = coll.json()["id"]
    upload = await test_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": (f"{title}.md", io.BytesIO(content), "text/markdown")},
        data={"title": title},
    )
    return collection_id, upload.json()["document_id"]


@pytest.mark.asyncio
async def test_semantic_search_returns_ranked_results(test_client):
    content = (
        b"# Refund Policy\n\n"
        b"Customers may request a full refund within 30 days of purchase. "
        b"Contact billing for enterprise accounts."
    )
    await _seed_collection(test_client, "Refund Policy", content)

    resp = await test_client.post(
        "/api/v1/knowledge/search",
        json={
            "query": (
                "Customers may request a full refund within 30 days of purchase. "
                "Contact billing for enterprise accounts."
            ),
            "limit": 5,
            "min_similarity": 0.0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    results = body["results"]
    assert all("citation" in r for r in results)
    assert all("similarity" in r for r in results)
    similarities = [r["similarity"] for r in results]
    assert similarities == sorted(similarities, reverse=True)


@pytest.mark.asyncio
async def test_search_respects_min_similarity_threshold(test_client):
    await _seed_collection(test_client, "Shipping", b"Express shipping in 2 days.")

    resp = await test_client.post(
        "/api/v1/knowledge/search",
        json={"query": "quantum physics black holes", "min_similarity": 0.99, "limit": 5},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_citation_includes_document_metadata(test_client):
    content = b"Vacation policy details for all employees."
    coll = await test_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "handbook-coll"},
    )
    collection_id = coll.json()["id"]
    await test_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": ("handbook.txt", io.BytesIO(content), "text/plain")},
        data={"title": "Employee Handbook"},
    )

    resp = await test_client.post(
        "/api/v1/knowledge/search",
        json={
            "query": "Vacation policy details for all employees.",
            "limit": 1,
            "min_similarity": 0.0,
        },
    )
    assert resp.json()["total"] >= 1
    citation = resp.json()["results"][0]["citation"]
    assert "document_title" in citation
    assert citation["document_title"] == "Employee Handbook"
