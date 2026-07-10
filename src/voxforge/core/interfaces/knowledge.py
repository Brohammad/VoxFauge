"""Ports for enterprise knowledge base ingestion and retrieval."""

from typing import Protocol
from uuid import UUID

from voxforge.core.domain.knowledge import (
    ChunkingConfig,
    ChunkSearchResult,
    IngestJob,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ParsedDocument,
    RawChunk,
    SourceType,
)


class DocumentParser(Protocol):
    """Parse raw file bytes into normalized text."""

    @property
    def source_type(self) -> SourceType: ...

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument: ...


class ChunkingStrategy(Protocol):
    """Split a parsed document into chunks for embedding."""

    async def chunk(
        self,
        document: ParsedDocument,
        *,
        config: ChunkingConfig,
    ) -> list[RawChunk]: ...


class BlobStore(Protocol):
    """Object storage for uploaded source files."""

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


class KnowledgeChunkStore(Protocol):
    """Vector-backed chunk persistence and search."""

    async def upsert_chunks(
        self,
        *,
        org_id: UUID,
        document_version_id: UUID,
        chunks: list[tuple[RawChunk, list[float]]],
    ) -> int: ...

    async def delete_by_version(self, document_version_id: UUID) -> int: ...

    async def delete_chunks_by_indices(
        self,
        document_version_id: UUID,
        chunk_indices: list[int],
    ) -> int: ...

    async def get_chunk_hashes(
        self,
        document_version_id: UUID,
    ) -> dict[int, str]: ...

    async def search_similar(
        self,
        *,
        org_id: UUID,
        query_embedding: list[float],
        collection_id: UUID | None = None,
        document_version_ids: list[UUID] | None = None,
        limit: int,
        min_similarity: float,
    ) -> list[ChunkSearchResult]: ...


class KnowledgeDocumentStore(Protocol):
    """Document and version metadata persistence."""

    async def create_collection(
        self,
        *,
        org_id: UUID,
        name: str,
        chunking_config: ChunkingConfig | None = None,
    ) -> KnowledgeCollection: ...

    async def get_collection(
        self,
        collection_id: UUID,
        *,
        org_id: UUID,
    ) -> KnowledgeCollection | None: ...

    async def create_document(
        self,
        *,
        org_id: UUID,
        collection_id: UUID,
        title: str,
        source_type: SourceType,
        content_hash: str,
    ) -> KnowledgeDocument: ...

    async def get_document(
        self,
        document_id: UUID,
        *,
        org_id: UUID,
    ) -> KnowledgeDocument | None: ...

    async def create_version(
        self,
        *,
        document_id: UUID,
        version_number: int,
        content_hash: str,
        blob_path: str,
        metadata: dict | None = None,
    ) -> KnowledgeDocumentVersion: ...

    async def set_active_version(
        self,
        document_id: UUID,
        *,
        org_id: UUID,
        version_id: UUID,
    ) -> None: ...

    async def get_active_version(
        self,
        document_id: UUID,
        *,
        org_id: UUID,
    ) -> KnowledgeDocumentVersion | None: ...

    async def update_document_status(
        self,
        document_id: UUID,
        *,
        org_id: UUID,
        status: str,
    ) -> None: ...


class IngestJobStore(Protocol):
    """Background ingestion job queue."""

    async def enqueue(
        self,
        *,
        org_id: UUID,
        document_id: UUID,
        job_type: str,
        document_version_id: UUID | None = None,
    ) -> IngestJob: ...

    async def claim_next(self) -> IngestJob | None: ...

    async def update_progress(
        self,
        job_id: UUID,
        *,
        progress_pct: int,
        stage: str,
    ) -> None: ...

    async def complete(self, job_id: UUID) -> None: ...

    async def fail(self, job_id: UUID, *, error_message: str) -> None: ...

    async def get_job(
        self,
        job_id: UUID,
        *,
        org_id: UUID,
    ) -> IngestJob | None: ...

    async def list_jobs_for_document(
        self,
        document_id: UUID,
        *,
        org_id: UUID,
    ) -> list[IngestJob]: ...


class KnowledgeSearchServicePort(Protocol):
    """High-level semantic search with citations."""

    async def search(
        self,
        *,
        org_id: UUID,
        request: KnowledgeSearchRequest,
    ) -> KnowledgeSearchResponse: ...
