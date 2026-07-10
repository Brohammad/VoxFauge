"""Internal pgvector-backed knowledge base provider."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voxforge.config import Settings
from voxforge.core.domain.knowledge import KnowledgeSearchRequest
from voxforge.core.domain.support import KnowledgeArticle, KnowledgeSearchResult
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.providers.embeddings.factory import create_embedding_provider
from voxforge.infrastructure.tools.tool_context import tool_org_id
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService


class InternalKnowledgeBaseProvider:
    """Org-scoped KB search via KnowledgeSearchService and tool context."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings

    async def search(self, query: str, *, limit: int = 5) -> KnowledgeSearchResult:
        org_id = tool_org_id.get()
        if org_id is None:
            return KnowledgeSearchResult(query=query, articles=[], total=0)

        async with self._session_factory() as session:
            repo = KnowledgeRepository(session)
            embedder = create_embedding_provider(self._settings)
            search = KnowledgeSearchService(repo, embedder, self._settings)
            response = await search.search(
                org_id=org_id,
                request=KnowledgeSearchRequest(query=query, limit=limit),
            )
            await session.commit()

        articles = [
            KnowledgeArticle(
                id=str(result.citation.chunk_id),
                title=result.citation.document_title,
                content=result.citation.excerpt,
                category=result.citation.source_type.value,
                tags=[result.citation.citation_label],
                url=None,
            )
            for result in response.results
        ]
        return KnowledgeSearchResult(query=query, articles=articles, total=len(articles))

    async def get_article(self, article_id: str) -> KnowledgeArticle | None:
        org_id = tool_org_id.get()
        if org_id is None:
            return None
        try:
            chunk_id = UUID(article_id)
        except ValueError:
            return None

        async with self._session_factory() as session:
            from sqlalchemy import select

            from voxforge.infrastructure.db.models import KnowledgeChunkModel

            result = await session.execute(
                select(KnowledgeChunkModel).where(
                    KnowledgeChunkModel.id == chunk_id,
                    KnowledgeChunkModel.org_id == org_id,
                )
            )
            model = result.scalar_one_or_none()
            if model is None:
                return None
            return KnowledgeArticle(
                id=str(model.id),
                title="Knowledge chunk",
                content=model.content,
                category="internal",
                tags=[],
            )
