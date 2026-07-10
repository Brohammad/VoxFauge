"""Inject knowledge base context into agent prompts."""

from __future__ import annotations

from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.knowledge import KnowledgeSearchRequest
from voxforge.modules.knowledge.application.citation import format_context_snippets
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService
from voxforge.modules.memory.application.context_builder import ChatMessageLike


class KnowledgeContextBuilder:
    def __init__(self, search_service: KnowledgeSearchService, settings: Settings) -> None:
        self._search = search_service
        self._settings = settings

    async def build_context(
        self,
        *,
        org_id: UUID,
        query: str,
        limit: int | None = None,
    ) -> str:
        snippets = await self.retrieve_snippets(org_id=org_id, query=query, limit=limit)
        if not snippets:
            return ""
        lines = "\n".join(f"- {s}" for s in snippets)
        return f"Relevant knowledge base excerpts:\n{lines}"

    async def retrieve_snippets(
        self,
        *,
        org_id: UUID,
        query: str,
        limit: int | None = None,
    ) -> list[str]:
        if not query.strip():
            return []
        response = await self._search.search(
            org_id=org_id,
            request=KnowledgeSearchRequest(
                query=query,
                limit=limit or self._settings.knowledge_search_top_k,
            ),
        )
        if not response.results:
            return []
        return format_context_snippets([r.citation for r in response.results])

    async def enrich_messages(
        self,
        messages: list[ChatMessageLike],
        *,
        org_id: UUID | None,
        query: str,
    ) -> list[ChatMessageLike]:
        if org_id is None or not query.strip():
            return messages

        context = await self.build_context(org_id=org_id, query=query)
        if not context:
            return messages

        insert_at = next(
            (i for i, message in enumerate(messages) if message.role != MessageRole.SYSTEM),
            len(messages),
        )
        kb_message = ChatMessageLike(role=MessageRole.SYSTEM, content=context)
        return [*messages[:insert_at], kb_message, *messages[insert_at:]]
