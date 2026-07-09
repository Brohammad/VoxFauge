"""Zendesk adapter stub — implement when connecting to Zendesk API."""

from voxforge.core.domain.support import (
    KnowledgeArticle,
    KnowledgeSearchResult,
    SupportTicket,
    TicketCreateRequest,
)
from voxforge.core.exceptions import ProviderError


class ZendeskKnowledgeBaseProvider:
    def __init__(self, subdomain: str, api_token: str) -> None:
        self._subdomain = subdomain
        self._api_token = api_token

    async def search(self, query: str, *, limit: int = 5) -> KnowledgeSearchResult:
        raise ProviderError(
            "zendesk",
            "Zendesk knowledge base integration is not yet implemented",
        )

    async def get_article(self, article_id: str) -> KnowledgeArticle | None:
        raise ProviderError(
            "zendesk",
            "Zendesk knowledge base integration is not yet implemented",
        )


class ZendeskTicketingProvider:
    def __init__(self, subdomain: str, api_token: str) -> None:
        self._subdomain = subdomain
        self._api_token = api_token

    async def lookup_ticket(self, ticket_id: str) -> SupportTicket | None:
        raise ProviderError("zendesk", "Zendesk ticketing integration is not yet implemented")

    async def lookup_by_customer_email(
        self, email: str, *, limit: int = 5
    ) -> list[SupportTicket]:
        raise ProviderError("zendesk", "Zendesk ticketing integration is not yet implemented")

    async def create_ticket(self, request: TicketCreateRequest) -> SupportTicket:
        raise ProviderError("zendesk", "Zendesk ticketing integration is not yet implemented")
