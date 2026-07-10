"""Factory helpers for knowledge application services."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.providers.embeddings.factory import create_embedding_provider
from voxforge.modules.knowledge.application.context_builder import KnowledgeContextBuilder
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService


def create_knowledge_context_builder(
    db_session: AsyncSession,
    settings: Settings,
) -> KnowledgeContextBuilder | None:
    if not settings.knowledge_enabled or not settings.knowledge_context_enabled:
        return None
    search = KnowledgeSearchService(
        KnowledgeRepository(db_session),
        create_embedding_provider(settings),
        settings,
    )
    return KnowledgeContextBuilder(search, settings)
