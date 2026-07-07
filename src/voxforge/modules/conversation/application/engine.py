from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.entities import Message, MessageRole
from voxforge.core.domain.events import TokenEvent
from voxforge.core.interfaces.providers import LLMProvider
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class _ChatMessage:
    role: MessageRole
    content: str


class ConversationEngine:
    def __init__(self, llm_provider: LLMProvider, settings: Settings) -> None:
        self._llm = llm_provider
        self._settings = settings
        self._history: dict[UUID, list[_ChatMessage]] = {}

    def init_session(self, session_id: UUID) -> None:
        self._history[session_id] = [
            _ChatMessage(role=MessageRole.SYSTEM, content=self._settings.system_prompt)
        ]

    def add_user_message(self, session_id: UUID, content: str) -> None:
        if session_id not in self._history:
            self.init_session(session_id)
        self._history[session_id].append(_ChatMessage(role=MessageRole.USER, content=content))

    def add_assistant_message(self, session_id: UUID, content: str) -> None:
        if session_id not in self._history:
            self.init_session(session_id)
        self._history[session_id].append(
            _ChatMessage(role=MessageRole.ASSISTANT, content=content)
        )

    def load_history(self, session_id: UUID, messages: list[Message]) -> None:
        self._history[session_id] = [
            _ChatMessage(role=MessageRole.SYSTEM, content=self._settings.system_prompt)
        ]
        for msg in messages:
            self._history[session_id].append(_ChatMessage(role=msg.role, content=msg.content))

    async def generate_response(
        self,
        session_id: UUID,
        *,
        model: str | None = None,
    ) -> AsyncIterator[TokenEvent]:
        history = self._history.get(session_id, [])
        model = model or self._settings.default_llm_model

        logger.info("conversation_generate", session_id=str(session_id), model=model)
        async for event in self._llm.generate_stream(history, model=model):
            yield event

    def clear_session(self, session_id: UUID) -> None:
        self._history.pop(session_id, None)
