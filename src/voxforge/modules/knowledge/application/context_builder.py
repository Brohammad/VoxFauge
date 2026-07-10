"""Inject knowledge base context into agent prompts."""

from __future__ import annotations

from uuid import UUID

from voxforge.core.domain.knowledge import KnowledgeSearchRequest
from voxforge.modules.knowledge.application.citation import format_context_snippets
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService


class KnowledgeContextBuilder:
    def __init__(self, search_service: KnowledgeSearchService) -> None:
        self._search = search_service

    async def build_context(
        self,
        *,
        org_id: UUID,
        query: str,
        limit: int = 3,
    ) -> str:
        response = await self._search.search(
            org_id=org_id,
            request=KnowledgeSearchRequest(query=query, limit=limit),
        )
        if not response.results:
            return ""
        snippets = format_context_snippets([r.citation for r in response.results])
        lines = "\n".join(f"- {s}" for s in snippets)
        return f"Relevant knowledge base excerpts:\n{lines}"
