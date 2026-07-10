"""Knowledge base REST API."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import (
    get_db_session,
    get_knowledge_ingestion_service,
    get_knowledge_repository,
    get_knowledge_search_service,
    require_scope,
)
from voxforge.config import Settings, get_settings
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.knowledge import KnowledgeSearchRequest
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.modules.knowledge.application.ingestion_service import KnowledgeIngestionService
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _require_knowledge(settings: Settings = Depends(get_settings)) -> None:
    if not settings.knowledge_enabled:
        raise HTTPException(status_code=503, detail="Knowledge base is disabled")


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    embedding_dimensions: int
    created_at: str


class UploadResponse(BaseModel):
    document_id: UUID
    job_id: UUID
    status: str


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    source_type: str
    status: str
    content_hash: str
    active_version_id: UUID | None
    created_at: str
    updated_at: str


class JobResponse(BaseModel):
    id: UUID
    document_id: UUID
    status: str
    progress_pct: int
    stage: str | None
    error_message: str | None


class SearchRequestBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    collection_id: UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.65, ge=0.0, le=1.0)


class CitationResponse(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    version: int
    source_type: str
    page: int | None
    heading: str | None
    excerpt: str
    similarity: float
    citation_label: str


class SearchResultResponse(BaseModel):
    similarity: float
    citation: CitationResponse


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultResponse]


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(
    body: CollectionCreateRequest,
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:write")),
    repo: KnowledgeRepository = Depends(get_knowledge_repository),
    db: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    collection = await repo.create_collection(org_id=principal.org_id, name=body.name)
    await db.commit()
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        embedding_dimensions=collection.embedding_dimensions,
        created_at=collection.created_at.isoformat(),
    )


@router.get("/collections", response_model=list[CollectionResponse])
async def list_collections(
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:read")),
    repo: KnowledgeRepository = Depends(get_knowledge_repository),
) -> list[CollectionResponse]:
    collections = await repo.list_collections(org_id=principal.org_id)
    return [
        CollectionResponse(
            id=c.id,
            name=c.name,
            embedding_dimensions=c.embedding_dimensions,
            created_at=c.created_at.isoformat(),
        )
        for c in collections
    ]


@router.post(
    "/collections/{collection_id}/documents", response_model=UploadResponse, status_code=202
)
async def upload_document(
    collection_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:write")),
    ingestion: KnowledgeIngestionService | None = Depends(get_knowledge_ingestion_service),
    db: AsyncSession = Depends(get_db_session),
) -> UploadResponse:
    if ingestion is None:
        raise HTTPException(status_code=503, detail="Knowledge base is disabled")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        document_id, job_id = await ingestion.upload_document(
            org_id=principal.org_id,
            collection_id=collection_id,
            filename=file.filename or "document.txt",
            content=content,
            title=title,
            content_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return UploadResponse(document_id=document_id, job_id=job_id, status="queued")


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:read")),
    repo: KnowledgeRepository = Depends(get_knowledge_repository),
) -> DocumentResponse:
    document = await repo.get_document(document_id, org_id=principal.org_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type.value,
        status=document.status.value,
        content_hash=document.content_hash,
        active_version_id=document.active_version_id,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


@router.get("/documents/{document_id}/jobs", response_model=list[JobResponse])
async def list_document_jobs(
    document_id: UUID,
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:read")),
    repo: KnowledgeRepository = Depends(get_knowledge_repository),
) -> list[JobResponse]:
    document = await repo.get_document(document_id, org_id=principal.org_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    jobs = await repo.list_jobs_for_document(document_id, org_id=principal.org_id)
    return [
        JobResponse(
            id=j.id,
            document_id=j.document_id,
            status=j.status.value,
            progress_pct=j.progress_pct,
            stage=j.stage.value if j.stage else None,
            error_message=j.error_message,
        )
        for j in jobs
    ]


@router.post("/documents/{document_id}/reindex", response_model=JobResponse, status_code=202)
async def reindex_document(
    document_id: UUID,
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:write")),
    ingestion: KnowledgeIngestionService | None = Depends(get_knowledge_ingestion_service),
    db: AsyncSession = Depends(get_db_session),
) -> JobResponse:
    if ingestion is None:
        raise HTTPException(status_code=503, detail="Knowledge base is disabled")
    try:
        job = await ingestion.reindex_document(org_id=principal.org_id, document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return JobResponse(
        id=job.id,
        document_id=job.document_id,
        status=job.status.value,
        progress_pct=job.progress_pct,
        stage=job.stage.value if job.stage else None,
        error_message=job.error_message,
    )


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(
    body: SearchRequestBody,
    _: None = Depends(_require_knowledge),
    principal: Principal = Depends(require_scope("knowledge:read")),
    search: KnowledgeSearchService | None = Depends(get_knowledge_search_service),
) -> SearchResponse:
    if search is None:
        raise HTTPException(status_code=503, detail="Knowledge base is disabled")
    response = await search.search(
        org_id=principal.org_id,
        request=KnowledgeSearchRequest(
            query=body.query,
            collection_id=body.collection_id,
            limit=body.limit,
            min_similarity=body.min_similarity,
        ),
    )
    return SearchResponse(
        query=response.query,
        total=response.total,
        results=[
            SearchResultResponse(
                similarity=r.similarity,
                citation=CitationResponse(
                    chunk_id=r.citation.chunk_id,
                    document_id=r.citation.document_id,
                    document_title=r.citation.document_title,
                    version=r.citation.version,
                    source_type=r.citation.source_type.value,
                    page=r.citation.page,
                    heading=r.citation.heading,
                    excerpt=r.citation.excerpt,
                    similarity=r.citation.similarity,
                    citation_label=r.citation.citation_label,
                ),
            )
            for r in response.results
        ],
    )
