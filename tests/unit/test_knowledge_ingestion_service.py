"""Unit tests for knowledge ingestion service."""

from uuid import uuid4

import pytest

from voxforge.config import get_settings
from voxforge.core.domain.knowledge import DocumentStatus
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.knowledge.blob import FilesystemBlobStore
from voxforge.infrastructure.providers.embeddings.mock import MockEmbeddingProvider
from voxforge.modules.knowledge.application.ingestion_service import KnowledgeIngestionService


@pytest.fixture
def kb_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("KNOWLEDGE_BLOB_PATH", str(tmp_path / "blobs"))
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
async def ingestion_service(db_session, kb_settings, tmp_path):
    repo = KnowledgeRepository(db_session)
    blob = FilesystemBlobStore(str(tmp_path / "blobs"))
    embedder = MockEmbeddingProvider()
    return KnowledgeIngestionService(repo, blob, embedder, kb_settings)


@pytest.mark.asyncio
async def test_upload_document_processes_inline(ingestion_service, db_session):
    org_id = uuid4()
    repo = ingestion_service._repo  # noqa: SLF001
    collection = await repo.create_collection(org_id=org_id, name="docs")
    await db_session.commit()

    content = b"# Returns\n\nYou may return items within 30 days."
    doc_id, job_id = await ingestion_service.upload_document(
        org_id=org_id,
        collection_id=collection.id,
        filename="returns.md",
        content=content,
        title="Return Policy",
    )
    await db_session.commit()

    document = await repo.get_document(doc_id, org_id=org_id)
    assert document is not None
    assert document.status == DocumentStatus.READY

    job = await repo.get_job_by_id(job_id)
    assert job is not None
    assert job.progress_pct == 100


@pytest.mark.asyncio
async def test_upload_rejects_missing_collection(ingestion_service):
    with pytest.raises(ValueError, match="Collection not found"):
        await ingestion_service.upload_document(
            org_id=uuid4(),
            collection_id=uuid4(),
            filename="x.txt",
            content=b"hello",
        )


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(ingestion_service, db_session, kb_settings):
    org_id = uuid4()
    repo = ingestion_service._repo  # noqa: SLF001
    collection = await repo.create_collection(org_id=org_id, name="small")
    await db_session.commit()

    oversized = b"x" * (kb_settings.knowledge_max_upload_bytes + 1)
    with pytest.raises(ValueError, match="exceeds maximum"):
        await ingestion_service.upload_document(
            org_id=org_id,
            collection_id=collection.id,
            filename="big.txt",
            content=oversized,
        )


@pytest.mark.asyncio
async def test_reindex_document(ingestion_service, db_session):
    org_id = uuid4()
    repo = ingestion_service._repo  # noqa: SLF001
    collection = await repo.create_collection(org_id=org_id, name="reindex")
    await db_session.commit()

    content = b"Version one content for search testing."
    doc_id, _ = await ingestion_service.upload_document(
        org_id=org_id,
        collection_id=collection.id,
        filename="doc.txt",
        content=content,
    )
    await db_session.commit()

    job = await ingestion_service.reindex_document(org_id=org_id, document_id=doc_id)
    await db_session.commit()
    assert job.job_type.value == "reindex"


@pytest.mark.asyncio
async def test_process_job_missing_job_is_noop(ingestion_service):
    await ingestion_service.process_job(uuid4())


@pytest.mark.asyncio
async def test_process_job_failure_marks_document_failed(
    ingestion_service, db_session, monkeypatch
):
    org_id = uuid4()
    repo = ingestion_service._repo  # noqa: SLF001
    collection = await repo.create_collection(org_id=org_id, name="fail")
    await db_session.commit()

    content = b"Will fail during embedding."
    doc_id, job_id = await ingestion_service.upload_document(
        org_id=org_id,
        collection_id=collection.id,
        filename="fail.txt",
        content=content,
    )
    await db_session.commit()

    async def boom(_texts):
        raise TimeoutError("embedding timeout")

    monkeypatch.setattr(ingestion_service._embedder, "embed_batch", boom)  # noqa: SLF001

    with pytest.raises(TimeoutError):
        await ingestion_service.process_job(job_id)
    await db_session.commit()

    document = await repo.get_document(doc_id, org_id=org_id)
    assert document.status == DocumentStatus.FAILED
