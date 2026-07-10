"""Feature test: knowledge upload → parse → chunk → embed → search."""

import io

import pytest

pytestmark = pytest.mark.feature


@pytest.mark.asyncio
async def test_knowledge_upload_to_context_injection(test_client):
    """Upload document, verify indexing, search returns citation for voice context."""
    coll = await test_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "product-docs"},
    )
    assert coll.status_code == 201
    collection_id = coll.json()["id"]

    content = (
        b"# Shipping Policy\n\n"
        b"Standard shipping takes 5-7 business days. "
        b"Express shipping is available for an additional fee."
    )
    upload = await test_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": ("shipping.md", io.BytesIO(content), "text/markdown")},
        data={"title": "Shipping Policy"},
    )
    assert upload.status_code == 202
    document_id = upload.json()["document_id"]

    doc = await test_client.get(f"/api/v1/knowledge/documents/{document_id}")
    assert doc.status_code == 200
    assert doc.json()["status"] == "ready"

    search = await test_client.post(
        "/api/v1/knowledge/search",
        json={
            "query": (
                "Standard shipping takes 5-7 business days. "
                "Express shipping is available for an additional fee."
            ),
            "limit": 3,
            "min_similarity": 0.0,
        },
    )
    assert search.status_code == 200
    results = search.json()["results"]
    assert len(results) >= 1
    assert results[0]["citation"]["document_title"] == "Shipping Policy"
    assert "chunk_id" in results[0]["citation"]
