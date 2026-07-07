from collections.abc import AsyncIterator

import pytest

from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.events import TokenEvent
from voxforge.core.interfaces.providers import ChatMessage
from voxforge.modules.conversation.application.engine import ConversationEngine


class MockLLM:
    async def generate_stream(
        self, messages: list[ChatMessage], *, model: str
    ) -> AsyncIterator[TokenEvent]:
        yield TokenEvent(text="Hello ", is_final=False)
        yield TokenEvent(text="world!", is_final=False)
        yield TokenEvent(text="", is_final=True)


@pytest.fixture
def settings():
    from voxforge.config import Settings

    return Settings()


@pytest.mark.asyncio
async def test_generate_response(settings):
    engine = ConversationEngine(MockLLM(), settings)
    session_id = __import__("uuid").uuid4()
    engine.init_session(session_id)
    engine.add_user_message(session_id, "Hi")

    tokens = []
    async for event in engine.generate_response(session_id):
        if event.text:
            tokens.append(event.text)

    assert "".join(tokens) == "Hello world!"


@pytest.mark.asyncio
async def test_load_history(settings):
    from uuid import uuid4

    from voxforge.core.domain.entities import Message

    engine = ConversationEngine(MockLLM(), settings)
    session_id = uuid4()

    messages = [
        Message(
            id=uuid4(),
            session_id=session_id,
            role=MessageRole.USER,
            content="Previous message",
            created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
    ]
    engine.load_history(session_id, messages)
    engine.add_user_message(session_id, "New message")

    tokens = []
    async for event in engine.generate_response(session_id):
        if event.text:
            tokens.append(event.text)

    assert len(tokens) > 0
