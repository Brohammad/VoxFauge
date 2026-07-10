"""Integration tests for knowledge base semantic search and citations.

Requires migration 010 and seeded chunks. Skipped until Phase 3 implementation.
See docs/architecture/knowledge-base.md.
"""

import pytest

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skip(reason="Knowledge base search not implemented — pending ADR-005 review"),
]


@pytest.mark.asyncio
async def test_semantic_search_returns_ranked_results(auth_client):
    """POST /knowledge/search returns chunks ordered by similarity."""
    resp = await auth_client.post(
        "/api/v1/knowledge/search",
        json={"query": "refund policy", "limit": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    results = body["results"]
    assert all("citation" in r for r in results)
    assert all("similarity" in r for r in results)
    # Verify descending similarity
    similarities = [r["similarity"] for r in results]
    assert similarities == sorted(similarities, reverse=True)


@pytest.mark.asyncio
async def test_search_respects_min_similarity_threshold(auth_client):
    """Results below min_similarity are excluded."""
    resp = await auth_client.post(
        "/api/v1/knowledge/search",
        json={"query": "unrelated topic xyz", "min_similarity": 0.95},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_scoped_to_collection(auth_client):
    """collection_id filter limits results to one collection."""
    pytest.skip("Requires seeded multi-collection data")


@pytest.mark.asyncio
async def test_pgvector_search_org_isolation(postgres_session):
    """Chunks from other orgs never appear in search results."""
    pytest.skip("Requires KnowledgeRepository implementation")


@pytest.mark.asyncio
async def test_citation_includes_page_and_version(auth_client):
    """PDF citations include page number and document version."""
    resp = await auth_client.post(
        "/api/v1/knowledge/search",
        json={"query": "employee handbook", "limit": 1},
    )
    citation = resp.json()["results"][0]["citation"]
    assert "citation_label" in citation
    assert "document_title" in citation
    assert "version" in citation
