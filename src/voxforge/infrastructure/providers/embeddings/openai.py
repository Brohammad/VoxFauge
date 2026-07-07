from voxforge.core.exceptions import ProviderError
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class OpenAIEmbeddingProvider:
    def __init__(self, api_key: str, *, model: str = "text-embedding-3-small") -> None:
        self._model = model
        self._client = None
        if api_key:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            raise ProviderError("openai", "API key not configured for embeddings")

        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            logger.error("openai_embedding_error", error=str(exc))
            raise ProviderError("openai", str(exc)) from exc
