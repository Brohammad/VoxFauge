"""Domain models for the enterprise knowledge base."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    TXT = "txt"
    CSV = "csv"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class IngestJobType(StrEnum):
    INGEST = "ingest"
    REINDEX = "reindex"
    INCREMENTAL = "incremental"


class IngestJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestStage(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"


class ChunkingConfig(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = 512
    chunk_overlap: int = 64
    rows_per_chunk: int = 50
    include_header: bool = True


class KnowledgeCollection(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    embedding_dimensions: int = 1536
    chunking_config: ChunkingConfig = Field(default_factory=ChunkingConfig)
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocument(BaseModel):
    id: UUID
    org_id: UUID
    collection_id: UUID
    title: str
    source_type: SourceType
    content_hash: str
    active_version_id: UUID | None = None
    status: DocumentStatus = DocumentStatus.PENDING
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeDocumentVersion(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    content_hash: str
    blob_path: str
    chunk_count: int = 0
    metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChunkMetadata(BaseModel):
    document_id: UUID | None = None
    version: int | None = None
    chunk_index: int | None = None
    page: int | None = None
    heading: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    source_type: SourceType | None = None


class KnowledgeChunk(BaseModel):
    id: UUID
    org_id: UUID
    document_version_id: UUID
    chunk_index: int
    content: str
    content_hash: str
    token_count: int | None = None
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestJob(BaseModel):
    id: UUID
    org_id: UUID
    document_id: UUID
    document_version_id: UUID | None = None
    job_type: IngestJobType
    status: IngestJobStatus = IngestJobStatus.QUEUED
    progress_pct: int = 0
    stage: IngestStage | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ParsedDocument(BaseModel):
    """Output of a DocumentParser — normalized text with structural metadata."""

    title: str
    text: str
    source_type: SourceType
    pages: list[str] = Field(default_factory=list)
    headings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class RawChunk(BaseModel):
    """Pre-embedding chunk produced by a ChunkingStrategy."""

    content: str
    chunk_index: int
    metadata: ChunkMetadata = Field(default_factory=ChunkMetadata)
    token_count: int | None = None


class Citation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    version: int
    source_type: SourceType
    page: int | None = None
    heading: str | None = None
    excerpt: str
    similarity: float
    citation_label: str


class ChunkSearchResult(BaseModel):
    chunk: KnowledgeChunk
    similarity: float
    citation: Citation


class KnowledgeSearchRequest(BaseModel):
    query: str
    collection_id: UUID | None = None
    limit: int = 5
    min_similarity: float = 0.65


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[ChunkSearchResult] = Field(default_factory=list)
    total: int = 0
