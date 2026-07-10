"""Factory for embedding providers."""

from voxforge.config import Settings
from voxforge.core.exceptions import ProviderError
from voxforge.core.interfaces.memory import EmbeddingProvider
from voxforge.infrastructure.providers.embeddings.mock import MockEmbeddingProvider
from voxforge.infrastructure.providers.embeddings.openai import OpenAIEmbeddingProvider


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider == "openai":
        return OpenAIEmbeddingProvider(
            settings.openai_api_key,
            model=settings.memory_embedding_model,
        )
    if provider == "mock":
        return MockEmbeddingProvider(dimensions=settings.memory_embedding_dimensions)
    raise ProviderError("factory", f"Unknown embedding provider: {provider}")
