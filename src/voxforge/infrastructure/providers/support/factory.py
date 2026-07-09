"""Factory for knowledge base and ticketing provider backends."""

from voxforge.config import Settings
from voxforge.core.exceptions import ProviderError
from voxforge.core.interfaces.support import KnowledgeBaseProvider, TicketingProvider
from voxforge.infrastructure.providers.support.freshdesk import (
    FreshdeskKnowledgeBaseProvider,
    FreshdeskTicketingProvider,
)
from voxforge.infrastructure.providers.support.mock import (
    MockKnowledgeBaseProvider,
    MockTicketingProvider,
)
from voxforge.infrastructure.providers.support.zendesk import (
    ZendeskKnowledgeBaseProvider,
    ZendeskTicketingProvider,
)


def create_knowledge_base_provider(settings: Settings) -> KnowledgeBaseProvider:
    provider = settings.knowledge_base_provider.lower()
    if provider == "mock":
        return MockKnowledgeBaseProvider()
    if provider == "zendesk":
        return ZendeskKnowledgeBaseProvider(
            settings.zendesk_subdomain,
            settings.zendesk_api_token,
        )
    if provider == "freshdesk":
        return FreshdeskKnowledgeBaseProvider(
            settings.freshdesk_domain,
            settings.freshdesk_api_key,
        )
    raise ProviderError("factory", f"Unknown knowledge base provider: {provider}")


def create_ticketing_provider(settings: Settings) -> TicketingProvider:
    provider = settings.ticketing_provider.lower()
    if provider == "mock":
        return MockTicketingProvider()
    if provider == "zendesk":
        return ZendeskTicketingProvider(
            settings.zendesk_subdomain,
            settings.zendesk_api_token,
        )
    if provider == "freshdesk":
        return FreshdeskTicketingProvider(
            settings.freshdesk_domain,
            settings.freshdesk_api_key,
        )
    raise ProviderError("factory", f"Unknown ticketing provider: {provider}")
