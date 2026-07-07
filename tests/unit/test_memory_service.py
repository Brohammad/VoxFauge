"""Unit tests for MemoryService with mocked providers."""

from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.entities import MessageRole
from voxforge.modules.memory.application.context_builder import ChatMessageLike
from voxforge.modules.memory.application.service import MemoryService


class MockEmbedder:
    async def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class MockStore:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.summary: str | None = None

    async def store_entry(self, **kwargs):
        from datetime import UTC, datetime

        from voxforge.core.domain.memory import MemoryEntry

        entry = MemoryEntry(
            id=uuid4(),
            org_id=kwargs["org_id"],
            session_id=kwargs["session_id"],
            role=kwargs["role"],
            content=kwargs["content"],
            entry_type=kwargs["entry_type"],
            message_id=kwargs.get("message_id"),
            metadata=kwargs.get("metadata") or {},
            created_at=datetime.now(UTC),
        )
        self.entries.append(kwargs)
        return entry

    async def search_similar(self, **kwargs):
        from datetime import UTC, datetime

        from voxforge.core.domain.memory import MemoryEntry

        if not self.entries:
            return []
        entry = self.entries[0]
        return [
            MemoryEntry(
                id=uuid4(),
                org_id=entry["org_id"],
                session_id=entry["session_id"],
                role=entry["role"],
                content=entry["content"],
                entry_type=entry["entry_type"],
                similarity=0.9,
                created_at=datetime.now(UTC),
            )
        ]

    async def list_entries(self, **kwargs):
        return []

    async def get_summary(self, session_id):
        return self.summary

    async def upsert_summary(self, **kwargs):
        self.summary = kwargs["summary"]

    async def count_turns(self, session_id):
        return len(self.entries)


@pytest.mark.asyncio
async def test_store_turn_persists_embedding():
    settings = Settings(memory_enabled=True)
    store = MockStore()
    service = MemoryService(store, MockEmbedder(), settings)

    org_id = uuid4()
    session_id = uuid4()
    await service.store_turn(
        org_id=org_id,
        session_id=session_id,
        role="user",
        content="Hello",
    )

    assert len(store.entries) == 1
    assert store.entries[0]["embedding"] == [1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_build_messages_injects_memory():
    settings = Settings(memory_enabled=True, memory_max_recent_messages=5)
    store = MockStore()
    service = MemoryService(store, MockEmbedder(), settings)

    org_id = uuid4()
    session_id = uuid4()
    await service.store_turn(
        org_id=org_id,
        session_id=session_id,
        role="user",
        content="Remember I like jazz.",
    )

    messages = await service.build_messages_for_llm(
        org_id=org_id,
        session_id=session_id,
        system_prompt="You are helpful.",
        recent_messages=[
            ChatMessageLike(role=MessageRole.USER, content="What music do I like?"),
        ],
        query="What music do I like?",
    )

    assert any("jazz" in m.content for m in messages)
    assert messages[-1].content == "What music do I like?"
