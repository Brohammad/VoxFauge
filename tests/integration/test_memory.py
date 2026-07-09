"""Integration tests for memory persistence."""

import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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


@pytest.mark.asyncio
async def test_memory_search_api(auth_client):
    from fastapi import Depends

    from voxforge.api.dependencies import get_memory_service
    from voxforge.config import Settings
    from voxforge.infrastructure.db.session import get_db_session
    from voxforge.main import app

    def _memory_service_override(db=Depends(get_db_session)):
        return MemoryService(
            MemoryRepository(db),
            FixedEmbedder([1.0, 0.0, 0.0]),
            Settings(memory_enabled=True),
        )

    app.dependency_overrides[get_memory_service] = _memory_service_override
    try:
        register_resp = await auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "memory-search@example.com",
                "password": "securepass123",
                "full_name": "Memory User",
                "org_name": "Memory Org",
            },
        )
        token = register_resp.json()["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
        session_id = session_resp.json()["session_id"]

        search_resp = await auth_client.post(
            f"/api/v1/sessions/{session_id}/memory/search",
            json={"query": "billing question", "limit": 3},
            headers=headers,
        )
        assert search_resp.status_code == 200
        assert "entries" in search_resp.json()
    finally:
        app.dependency_overrides.pop(get_memory_service, None)


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_memory_repository_postgres_vector_search():
    """Exercises the pgvector CAST(...) SQL path against a real Postgres instance."""
    from voxforge.infrastructure.db.models import OrganizationModel, VoiceSessionModel
    from tests.helpers.postgres import run_alembic_migrations

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        pytest.skip("requires PostgreSQL DATABASE_URL")

    run_alembic_migrations()

    engine = create_async_engine(database_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    org_id = uuid4()
    session_id = uuid4()

    async with factory() as db_session:
        db_session.add(
            OrganizationModel(id=org_id, name="Test Org", slug=f"org-{org_id.hex[:8]}")
        )
        db_session.add(
            VoiceSessionModel(
                id=session_id, org_id=org_id, status="active", transport_type="websocket"
            )
        )
        await db_session.flush()

        repo = MemoryRepository(db_session)
        dim = 1536
        vector_a = [0.0] * dim
        vector_a[0] = 1.0
        vector_b = [0.0] * dim
        vector_b[1] = 1.0

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
        await db_session.commit()

        results = await repo.search_similar(
            org_id=org_id,
            session_id=session_id,
            query_embedding=vector_a,
            limit=2,
            min_similarity=0.5,
        )

        assert len(results) >= 1
        assert results[0].content == "I love hiking."

    await engine.dispose()
