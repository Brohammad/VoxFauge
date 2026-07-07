from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from voxforge.core.domain.events import TokenEvent
from voxforge.core.exceptions import ProviderError
from voxforge.core.interfaces.providers import ChatMessage
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class OpenAILLMProvider:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def generate_stream(
        self,
        messages: list[ChatMessage],
        *,
        model: str,
    ) -> AsyncIterator[TokenEvent]:
        if self._client is None:
            raise ProviderError("openai", "API key not configured")

        formatted = [{"role": m.role.value, "content": m.content} for m in messages]

        try:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=formatted,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield TokenEvent(text=delta.content, is_final=False)
            yield TokenEvent(text="", is_final=True)
        except Exception as exc:
            logger.error("openai_stream_error", error=str(exc))
            raise ProviderError("openai", str(exc)) from exc
