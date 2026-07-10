from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.events import TokenEvent
from voxforge.core.interfaces.providers import ChatMessage
from voxforge.modules.conversation.application.engine import ConversationEngine


class MockLLM:
    def __init__(self) -> None:
        self.last_messages: list[ChatMessage] = []

    async def generate_stream(
        self, messages: list[ChatMessage], *, model: str
    ) -> AsyncIterator[TokenEvent]:
        self.last_messages = messages
        yield TokenEvent(text="ok", is_final=True)


class MockKnowledgeContextBuilder:
    def __init__(self, context: str) -> None:
        self._context = context
        self.calls: list[tuple] = []

    async def enrich_messages(self, messages, *, org_id, query):
        self.calls.append((org_id, query))
        if not org_id or not self._context:
            return messages
        from voxforge.modules.memory.application.context_builder import ChatMessageLike

        return [
            *messages,
            ChatMessageLike(role=MessageRole.SYSTEM, content=self._context),
        ]


@pytest.fixture
def settings():
    from voxforge.config import Settings

    return Settings(knowledge_context_enabled=True)


@pytest.mark.asyncio
async def test_conversation_engine_injects_knowledge_context(settings):
    llm = MockLLM()
    kb = MockKnowledgeContextBuilder("Relevant knowledge base excerpts:\n- [Policy]")
    engine = ConversationEngine(llm, settings, knowledge_context_builder=kb)
    session_id = uuid4()
    org_id = uuid4()

    engine.set_session_org(session_id, org_id)
    engine.init_session(session_id)
    engine.add_user_message(session_id, "What is the refund policy?")

    async for _ in engine.generate_response(session_id):
        pass

    assert kb.calls == [(org_id, "What is the refund policy?")]
    assert any("knowledge base excerpts" in m.content for m in llm.last_messages)


@pytest.mark.asyncio
async def test_conversation_engine_skips_knowledge_when_disabled(settings):
    settings.knowledge_context_enabled = False
    llm = MockLLM()
    kb = MockKnowledgeContextBuilder("Relevant knowledge base excerpts:\n- [Policy]")
    engine = ConversationEngine(llm, settings, knowledge_context_builder=kb)
    session_id = uuid4()

    engine.set_session_org(session_id, uuid4())
    engine.init_session(session_id)
    engine.add_user_message(session_id, "Hello")

    async for _ in engine.generate_response(session_id):
        pass

    assert kb.calls == []
