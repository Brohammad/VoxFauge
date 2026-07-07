from voxforge.core.interfaces.providers import LLMProvider
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

SUMMARIZE_PROMPT = (
    "Summarize the following conversation concisely for future context. "
    "Preserve key facts, user preferences, and unresolved questions. "
    "Keep the summary under 200 words.\n\n"
    "Conversation:\n{conversation}"
)


class Summarizer:
    def __init__(self, llm: LLMProvider, *, model: str) -> None:
        self._llm = llm
        self._model = model

    async def summarize(self, conversation_text: str) -> str:
        from dataclasses import dataclass

        from voxforge.core.domain.entities import MessageRole

        @dataclass
        class Msg:
            role: MessageRole
            content: str

        prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text)
        tokens: list[str] = []
        async for event in self._llm.generate_stream(
            [Msg(role=MessageRole.USER, content=prompt)],
            model=self._model,
        ):
            if event.text:
                tokens.append(event.text)

        summary = "".join(tokens).strip()
        logger.info("memory_summary_generated", length=len(summary))
        return summary or conversation_text[:500]
