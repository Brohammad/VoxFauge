"""Integration tests for memory persistence."""

from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.memory import MemoryEntryType
from voxforge.infrastructure.db.memory_repository import MemoryRepository
from voxforge.modules.memory.application.service import MemoryService


class FixedEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, text: str) -> list[float]:
        return self._vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


@pytest.mark.asyncio
async def test_memory_repository_store_and_search(db_session):
    org_id = uuid4()
    session_id = uuid4()

    # Seed org + session rows required by FK constraints
    from voxforge.infrastructure.db.models import OrganizationModel, VoiceSessionModel

    db_session.add(OrganizationModel(id=org_id, name="Test Org", slug=f"org-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(id=session_id, org_id=org_id, status="active", transport_type="websocket")
    )
    await db_session.flush()

    repo = MemoryRepository(db_session)
    vector_a = [1.0, 0.0, 0.0]
    vector_b = [0.0, 1.0, 0.0]

    await repo.store_entry(
        org_id=org_id,
        session_id=session_id,
        role="user",
        content="I love hiking.",
        entry_type=MemoryEntryType.TURN,
        embedding=vector_a,
    )
    await repo.store_entry(
        org_id=org_id,
        session_id=session_id,
        role="user",
        content="I enjoy cooking.",
        entry_type=MemoryEntryType.TURN,
        embedding=vector_b,
    )

    results = await repo.search_similar(
        org_id=org_id,
        session_id=session_id,
        query_embedding=vector_a,
        limit=2,
        min_similarity=0.5,
    )

    assert len(results) >= 1
    assert results[0].content == "I love hiking."


@pytest.mark.asyncio
async def test_memory_service_summary_storage(db_session):
    org_id = uuid4()
    session_id = uuid4()

    from voxforge.infrastructure.db.models import OrganizationModel, VoiceSessionModel

    db_session.add(OrganizationModel(id=org_id, name="Test Org", slug=f"org-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(id=session_id, org_id=org_id, status="active", transport_type="websocket")
    )
    await db_session.flush()

    repo = MemoryRepository(db_session)
    settings = Settings(memory_enabled=True)
    service = MemoryService(repo, FixedEmbedder([0.5, 0.5, 0.0]), settings)

    await repo.upsert_summary(
        org_id=org_id,
        session_id=session_id,
        summary="User discussed outdoor hobbies.",
        message_count=4,
    )

    summary = await service._store.get_summary(session_id)
    assert summary == "User discussed outdoor hobbies."
