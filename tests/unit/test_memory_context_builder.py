"""Unit tests for memory context assembly."""

from datetime import UTC, datetime
from uuid import uuid4

from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.memory import MemoryContext, MemoryEntry, MemoryEntryType
from voxforge.modules.memory.application.context_builder import ChatMessageLike, ContextBuilder


def test_context_builder_includes_summary_and_retrieval():
    builder = ContextBuilder()
    session_id = uuid4()
    org_id = uuid4()

    memory_context = MemoryContext(
        summary="User prefers concise answers.",
        relevant_entries=[
            MemoryEntry(
                id=uuid4(),
                org_id=org_id,
                session_id=session_id,
                role="user",
                content="My name is Alex.",
                entry_type=MemoryEntryType.TURN,
                created_at=datetime.now(UTC),
                similarity=0.92,
            )
        ],
    )

    messages = builder.build(
        system_prompt="You are helpful.",
        recent_messages=[
            ChatMessageLike(role=MessageRole.USER, content="What is my name?"),
        ],
        memory_context=memory_context,
        max_recent_messages=10,
    )

    assert messages[0].content == "You are helpful."
    assert "Conversation summary" in messages[1].content
    assert "Alex" in messages[2].content
    assert messages[-1].content == "What is my name?"


def test_context_builder_trims_recent_messages():
    builder = ContextBuilder()
    recent = [ChatMessageLike(role=MessageRole.USER, content=f"msg-{i}") for i in range(15)]

    messages = builder.build(
        system_prompt="System",
        recent_messages=recent,
        memory_context=MemoryContext(),
        max_recent_messages=5,
    )

    user_messages = [m for m in messages if m.role == MessageRole.USER]
    assert len(user_messages) == 5
    assert user_messages[0].content == "msg-10"
