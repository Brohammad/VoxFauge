"""Semantic search with citation generation."""

from __future__ import annotations

import time
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.knowledge import (
    ChunkSearchResult,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from voxforge.core.interfaces.memory import EmbeddingProvider
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.observability.metrics import knowledge_search_latency_seconds
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.modules.knowledge.application.citation import build_citation

_tracer = get_tracer(__name__)


class KnowledgeSearchService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        embedder: EmbeddingProvider,
        settings: Settings,
    ) -> None:
        self._repo = repository
        self._embedder = embedder
        self._settings = settings

    async def search(
        self,
        *,
        org_id: UUID,
        request: KnowledgeSearchRequest,
    ) -> KnowledgeSearchResponse:
        with _tracer.start_as_current_span("knowledge.search") as span:
            span.set_attribute("voxforge.knowledge.query", request.query[:200])
            start = time.monotonic()
            query_embedding = await self._embedder.embed(request.query)
            min_similarity = (
                request.min_similarity
                if request.min_similarity is not None
                else self._settings.knowledge_search_min_similarity
            )
            limit = request.limit or self._settings.knowledge_search_top_k

            scored = await self._repo.search_chunks(
                org_id=org_id,
                query_embedding=query_embedding,
                collection_id=request.collection_id,
                limit=limit,
                min_similarity=min_similarity,
            )

            results: list[ChunkSearchResult] = []
            for chunk, similarity, document, version in scored:
                citation = build_citation(
                    chunk=chunk,
                    document=document,
                    version=version,
                    similarity=similarity,
                )
                results.append(
                    ChunkSearchResult(chunk=chunk, similarity=similarity, citation=citation)
                )

            elapsed = time.monotonic() - start
            knowledge_search_latency_seconds.observe(elapsed)
            span.set_attribute("voxforge.knowledge.result_count", len(results))

            return KnowledgeSearchResponse(
                query=request.query,
                results=results,
                total=len(results),
            )
