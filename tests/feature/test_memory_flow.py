"""Feature test: conversation → memory write → retrieval → prompt injection."""

from uuid import UUID, uuid4

import pytest
from fastapi import Depends

from voxforge.api.dependencies import get_memory_service
from voxforge.config import Settings, get_settings
from voxforge.core.domain.memory import MemoryEntryType
from voxforge.infrastructure.db.memory_repository import MemoryRepository
from voxforge.infrastructure.db.session import get_db_session
from voxforge.main import app
from voxforge.modules.memory.application.service import MemoryService

pytestmark = pytest.mark.feature


class FixedEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, text: str) -> list[float]:
        return self._vector

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


@pytest.fixture(autouse=True)
def enable_memory(monkeypatch):
    monkeypatch.setenv("MEMORY_ENABLED", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_memory_write_and_semantic_search(auth_client, db_session):
    vector = [1.0, 0.0, 0.0]

    def _memory_service_override(db=Depends(get_db_session)):
        return MemoryService(
            MemoryRepository(db),
            FixedEmbedder(vector),
            Settings(memory_enabled=True),
        )

    app.dependency_overrides[get_memory_service] = _memory_service_override
    try:
        register = await auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"memory-{uuid4().hex[:8]}@example.com",
                "password": "securepass123",
                "full_name": "Memory User",
                "org_name": "Memory Org",
            },
        )
        token = register.json()["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        org_id = UUID(register.json()["org_id"])
        session_resp = await auth_client.post("/api/v1/sessions", json={}, headers=headers)
        session_id = UUID(session_resp.json()["session_id"])

        repo = MemoryRepository(db_session)
        await repo.store_entry(
            org_id=org_id,
            session_id=session_id,
            role="user",
            content="My account number is ACC-12345",
            entry_type=MemoryEntryType.TURN,
            embedding=vector,
        )
        await db_session.commit()

        search = await auth_client.post(
            f"/api/v1/sessions/{session_id}/memory/search",
            json={"query": "account number", "limit": 5},
            headers=headers,
        )
        assert search.status_code == 200
        entries = search.json()["entries"]
        assert len(entries) >= 1
        assert "ACC-12345" in entries[0]["content"]
    finally:
        app.dependency_overrides.pop(get_memory_service, None)
