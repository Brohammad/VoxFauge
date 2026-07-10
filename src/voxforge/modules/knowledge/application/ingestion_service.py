"""Knowledge base ingestion orchestration."""

from __future__ import annotations

import time
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.knowledge import (
    ChunkingConfig,
    DocumentStatus,
    IngestJob,
    IngestJobType,
    IngestStage,
    SourceType,
)
from voxforge.core.interfaces.knowledge import BlobStore
from voxforge.core.interfaces.memory import EmbeddingProvider
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.knowledge.chunking import get_chunker
from voxforge.infrastructure.knowledge.parsers import get_parser
from voxforge.infrastructure.knowledge.util import (
    detect_source_type,
    normalize_text,
    safe_upload_filename,
    sha256_text,
)
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    knowledge_chunks_indexed_total,
    knowledge_ingest_duration_seconds,
    knowledge_ingest_jobs_total,
)
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.modules.knowledge.application.citation import compute_chunk_diff, next_version_number

logger = get_logger(__name__)
_tracer = get_tracer(__name__)


class KnowledgeIngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        blob_store: BlobStore,
        embedder: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._repo = repository
        self._blob = blob_store
        self._embedder = embedder
        self._settings = settings
        self._chunker = get_chunker()

    async def upload_document(
        self,
        *,
        org_id: UUID,
        collection_id: UUID,
        filename: str,
        content: bytes,
        title: str | None = None,
        content_type: str | None = None,
    ) -> tuple[UUID, UUID]:
        collection = await self._repo.get_collection(collection_id, org_id=org_id)
        if collection is None:
            raise ValueError("Collection not found")

        filename = safe_upload_filename(filename)
        if len(content) > self._settings.knowledge_max_upload_bytes:
            max_bytes = self._settings.knowledge_max_upload_bytes
            raise ValueError(f"File exceeds maximum upload size of {max_bytes} bytes")

        source_type = SourceType(detect_source_type(filename, content_type))
        parser = get_parser(source_type)
        parsed = await parser.parse(content, filename=filename)
        normalized_hash = sha256_text(normalize_text(parsed.text))
        doc_title = title or parsed.title

        document = await self._repo.create_document(
            org_id=org_id,
            collection_id=collection_id,
            title=doc_title,
            source_type=source_type,
            content_hash=normalized_hash,
        )

        version_number = next_version_number(
            await self._repo.get_latest_version_number(document.id)
        )
        blob_key = f"{org_id}/{document.id}/v{version_number}/{filename}"
        await self._blob.put(blob_key, content, content_type=content_type)

        version = await self._repo.create_version(
            document_id=document.id,
            version_number=version_number,
            content_hash=normalized_hash,
            blob_path=blob_key,
            metadata={"filename": filename, "source_type": source_type.value},
        )

        job = await self._repo.enqueue(
            org_id=org_id,
            document_id=document.id,
            job_type=IngestJobType.INGEST.value,
            document_version_id=version.id,
        )
        knowledge_ingest_jobs_total.labels(status="queued", source_type=source_type.value).inc()

        if not self._settings.knowledge_worker_enabled:
            await self.process_job(job.id)

        return document.id, job.id

    async def reindex_document(self, *, org_id: UUID, document_id: UUID) -> IngestJob:
        document = await self._repo.get_document(document_id, org_id=org_id)
        if document is None:
            raise ValueError("Document not found")
        version = await self._repo.get_active_version(document_id, org_id=org_id)
        if version is None:
            raise ValueError("No active version to reindex")
        job = await self._repo.enqueue(
            org_id=org_id,
            document_id=document_id,
            job_type=IngestJobType.REINDEX.value,
            document_version_id=version.id,
        )
        if not self._settings.knowledge_worker_enabled:
            await self.process_job(job.id)
        return job

    async def process_job(self, job_id: UUID) -> None:
        with _tracer.start_as_current_span("knowledge.ingest") as span:
            span.set_attribute("voxforge.knowledge.job_id", str(job_id))
            await self._process_job_inner(job_id)

    async def _process_job_inner(self, job_id: UUID) -> None:
        start = time.monotonic()
        job = await self._repo.get_job_by_id(job_id)
        if job is None:
            return

        org_id = job.org_id
        document_id = job.document_id
        version_id = job.document_version_id

        try:
            document = await self._repo.get_document(document_id, org_id=org_id)
            if document is None or version_id is None:
                raise ValueError("Document or version missing")

            version = await self._repo.get_version(version_id)
            if version is None:
                raise ValueError("Version not found")

            await self._repo.update_document_status(
                document_id, org_id=org_id, status=DocumentStatus.PROCESSING.value
            )
            await self._repo.update_progress(
                job_id, progress_pct=10, stage=IngestStage.PARSING.value
            )

            raw_bytes = await self._blob.get(version.blob_path)
            parser = get_parser(document.source_type)
            parsed = await parser.parse(
                raw_bytes, filename=version.metadata.get("filename", "document")
            )

            await self._repo.update_progress(
                job_id, progress_pct=30, stage=IngestStage.CHUNKING.value
            )
            collection = await self._repo.get_collection(document.collection_id, org_id=org_id)
            config = (
                collection.chunking_config
                if collection
                else ChunkingConfig(
                    chunk_size=self._settings.knowledge_default_chunk_size,
                    chunk_overlap=self._settings.knowledge_default_chunk_overlap,
                )
            )
            chunks = await self._chunker.chunk(parsed, config=config)

            await self._repo.update_progress(
                job_id, progress_pct=50, stage=IngestStage.EMBEDDING.value
            )
            texts = [c.content for c in chunks]
            embeddings = await self._embedder.embed_batch(texts) if texts else []

            await self._repo.update_progress(
                job_id, progress_pct=75, stage=IngestStage.INDEXING.value
            )

            if job.job_type == IngestJobType.REINDEX:
                await self._repo.delete_by_version(version_id)
                pairs = list(zip(chunks, embeddings, strict=True))
            else:
                existing_hashes = await self._repo.get_chunk_hashes(version_id)
                new_pairs = [(c.chunk_index, sha256_text(c.content)) for c in chunks]
                _, changed, removed = compute_chunk_diff(existing_hashes, new_pairs)
                if removed:
                    await self._repo.delete_chunks_by_indices(version_id, removed)
                changed_set = set(changed)
                pairs = [
                    (c, e)
                    for c, e in zip(chunks, embeddings, strict=True)
                    if c.chunk_index in changed_set or not existing_hashes
                ]

            indexed = await self._repo.upsert_chunks(
                org_id=org_id,
                document_version_id=version_id,
                chunks=pairs,
            )
            if indexed:
                knowledge_chunks_indexed_total.inc(indexed)
            await self._repo.update_version_chunk_count(version_id, indexed)
            await self._repo.set_active_version(document_id, org_id=org_id, version_id=version_id)
            await self._repo.update_document_status(
                document_id, org_id=org_id, status=DocumentStatus.READY.value
            )
            await self._repo.complete_job(job_id)
            knowledge_ingest_jobs_total.labels(
                status="completed", source_type=document.source_type.value
            ).inc()
            knowledge_ingest_duration_seconds.labels(stage="total").observe(
                time.monotonic() - start
            )
        except Exception as exc:
            logger.error("knowledge_ingest_failed", job_id=str(job_id), error=str(exc))
            await self._repo.fail_job(job_id, error_message=str(exc))
            await self._repo.update_document_status(
                document_id, org_id=org_id, status=DocumentStatus.FAILED.value
            )
            knowledge_ingest_jobs_total.labels(status="failed", source_type="unknown").inc()
            raise
