"""Freshdesk adapter stub — implement when connecting to Freshdesk API."""

from voxforge.core.domain.support import (
    KnowledgeArticle,
    KnowledgeSearchResult,
    SupportTicket,
    TicketCreateRequest,
)
from voxforge.core.exceptions import ProviderError


class FreshdeskKnowledgeBaseProvider:
    def __init__(self, domain: str, api_key: str) -> None:
        self._domain = domain
        self._api_key = api_key

    async def search(self, query: str, *, limit: int = 5) -> KnowledgeSearchResult:
        raise ProviderError(
            "freshdesk",
            "Freshdesk knowledge base integration is not yet implemented",
        )

    async def get_article(self, article_id: str) -> KnowledgeArticle | None:
        raise ProviderError(
            "freshdesk",
            "Freshdesk knowledge base integration is not yet implemented",
        )


class FreshdeskTicketingProvider:
    def __init__(self, domain: str, api_key: str) -> None:
        self._domain = domain
        self._api_key = api_key

    async def lookup_ticket(self, ticket_id: str) -> SupportTicket | None:
        raise ProviderError("freshdesk", "Freshdesk ticketing integration is not yet implemented")

    async def lookup_by_customer_email(self, email: str, *, limit: int = 5) -> list[SupportTicket]:
        raise ProviderError("freshdesk", "Freshdesk ticketing integration is not yet implemented")

    async def create_ticket(self, request: TicketCreateRequest) -> SupportTicket:
        raise ProviderError("freshdesk", "Freshdesk ticketing integration is not yet implemented")
