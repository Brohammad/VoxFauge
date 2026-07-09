"""Integration tests for knowledge base ingestion pipeline.

These tests require migration 010 (knowledge base schema) and are skipped until
Phase 1 implementation is complete. See docs/architecture/knowledge-base.md.
"""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.skip(
    reason="Knowledge base ingestion not implemented — pending ADR-005 review"
)


@pytest.fixture
def sample_pdf_bytes():
    """Minimal PDF bytes for parser tests (placeholder)."""
    return b"%PDF-1.4 minimal"


@pytest.mark.asyncio
async def test_upload_creates_document_and_job(auth_client, sample_pdf_bytes):
    """POST /knowledge/collections/{id}/documents enqueues ingest job."""
    collection_resp = await auth_client.post(
        "/api/v1/knowledge/collections",
        json={"name": "test-collection"},
    )
    assert collection_resp.status_code == 201
    collection_id = collection_resp.json()["id"]

    upload_resp = await auth_client.post(
        f"/api/v1/knowledge/collections/{collection_id}/documents",
        files={"file": ("handbook.pdf", sample_pdf_bytes, "application/pdf")},
        data={"title": "Employee Handbook"},
    )
    assert upload_resp.status_code == 202
    body = upload_resp.json()
    assert "document_id" in body
    assert "job_id" in body
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_ingest_job_progress_tracking(auth_client, sample_pdf_bytes):
    """Ingest job progresses through parsing → chunking → embedding → indexing."""
    pytest.skip("Requires worker process")


@pytest.mark.asyncio
async def test_incremental_update_skips_unchanged_chunks():
    """Re-upload with same content hash does not create new version."""
    pytest.skip("Requires ingestion service")


@pytest.mark.asyncio
async def test_reindex_creates_new_embeddings():
    """POST /documents/{id}/reindex re-embeds all chunks."""
    pytest.skip("Requires ingestion service")


@pytest.mark.asyncio
async def test_org_isolation_on_document_access(auth_client):
    """Cross-org document access returns 404."""
    foreign_doc_id = uuid4()
    resp = await auth_client.get(f"/api/v1/knowledge/documents/{foreign_doc_id}")
    assert resp.status_code == 404
