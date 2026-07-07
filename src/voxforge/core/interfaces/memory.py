from typing import Protocol
from uuid import UUID

from voxforge.core.domain.memory import MemoryEntry, MemoryEntryType


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class MemoryStore(Protocol):
    async def store_entry(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        role: str,
        content: str,
        entry_type: MemoryEntryType,
        embedding: list[float],
        message_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> MemoryEntry: ...

    async def search_similar(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        query_embedding: list[float],
        limit: int,
        min_similarity: float,
    ) -> list[MemoryEntry]: ...

    async def list_entries(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryEntry]: ...

    async def get_summary(self, session_id: UUID) -> str | None: ...

    async def upsert_summary(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        summary: str,
        message_count: int,
    ) -> None: ...

    async def count_turns(self, session_id: UUID) -> int: ...
