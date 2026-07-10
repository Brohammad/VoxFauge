"""Unit tests for extractive conversation summarizer."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.core.domain.entities import Message, MessageRole
from voxforge.modules.handoff.application.summarizer import ExtractiveConversationSummarizer


class _FakeSessionManager:
    def __init__(self, messages: list[Message]) -> None:
        self._messages = messages

    async def get_messages(self, session_id, offset=0, limit=50):
        _ = session_id, offset
        return self._messages[:limit]


@pytest.mark.asyncio
async def test_summarize_empty_messages():
    summarizer = ExtractiveConversationSummarizer(_FakeSessionManager([]))
    result = await summarizer.summarize(session_id=uuid4(), org_id=uuid4())
    assert result == "No prior conversation messages."


@pytest.mark.asyncio
async def test_summarize_formats_roles_and_truncates_long_content():
    long_content = "x" * 300
    messages = [
        Message(
            id=uuid4(),
            session_id=uuid4(),
            role=MessageRole.USER,
            content=long_content,
            created_at=datetime.now(UTC),
        ),
        Message(
            id=uuid4(),
            session_id=uuid4(),
            role=MessageRole.ASSISTANT,
            content="Short reply",
            created_at=datetime.now(UTC),
        ),
    ]
    summarizer = ExtractiveConversationSummarizer(_FakeSessionManager(messages))
    result = await summarizer.summarize(session_id=uuid4(), org_id=uuid4())
    assert "user:" in result
    assert "assistant: Short reply" in result
    assert len(result.split("\n")[0]) <= 250


@pytest.mark.asyncio
async def test_summarize_caps_total_length():
    messages = [
        Message(
            id=uuid4(),
            session_id=uuid4(),
            role=MessageRole.USER,
            content=f"line {i} " + "word " * 50,
            created_at=datetime.now(UTC),
        )
        for i in range(100)
    ]
    summarizer = ExtractiveConversationSummarizer(_FakeSessionManager(messages))
    result = await summarizer.summarize(session_id=uuid4(), org_id=uuid4(), max_messages=100)
    assert len(result) <= 4000
