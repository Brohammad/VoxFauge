"""Ports for knowledge base and ticketing backends."""

from typing import Protocol

from voxforge.core.domain.support import (
    KnowledgeArticle,
    KnowledgeSearchResult,
    SupportTicket,
    TicketCreateRequest,
)


class KnowledgeBaseProvider(Protocol):
    """Search and retrieve knowledge base articles."""

    async def search(self, query: str, *, limit: int = 5) -> KnowledgeSearchResult: ...

    async def get_article(self, article_id: str) -> KnowledgeArticle | None: ...


class TicketingProvider(Protocol):
    """Look up and create support tickets."""

    async def lookup_ticket(self, ticket_id: str) -> SupportTicket | None: ...

    async def lookup_by_customer_email(
        self, email: str, *, limit: int = 5
    ) -> list[SupportTicket]: ...

    async def create_ticket(self, request: TicketCreateRequest) -> SupportTicket: ...
