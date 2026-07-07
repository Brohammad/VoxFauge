import time
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.memory import MemoryContext, MemoryEntryType
from voxforge.core.interfaces.memory import EmbeddingProvider, MemoryStore
from voxforge.core.interfaces.providers import LLMProvider
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    memory_retrieval_latency_seconds,
    memory_stores_total,
)
from voxforge.modules.memory.application.context_builder import ChatMessageLike, ContextBuilder
from voxforge.modules.memory.application.summarizer import Summarizer

logger = get_logger(__name__)


class MemoryService:
    def __init__(
        self,
        store: MemoryStore,
        embedder: EmbeddingProvider,
        settings: Settings,
        llm: LLMProvider | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._settings = settings
        self._context_builder = ContextBuilder()
        self._summarizer = Summarizer(llm, model=settings.memory_summary_model) if llm else None

    async def store_turn(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        role: str,
        content: str,
        message_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> None:
        if not self._settings.memory_enabled:
            return

        embedding = await self._embedder.embed(content)
        await self._store.store_entry(
            org_id=org_id,
            session_id=session_id,
            role=role,
            content=content,
            entry_type=MemoryEntryType.TURN,
            embedding=embedding,
            message_id=message_id,
            metadata=metadata,
        )
        memory_stores_total.inc()
        logger.info(
            "memory_turn_stored",
            session_id=str(session_id),
            role=role,
        )

        if self._summarizer and role == MessageRole.ASSISTANT.value:
            await self._maybe_summarize(org_id, session_id)

    async def retrieve_context(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        query: str,
    ) -> MemoryContext:
        if not self._settings.memory_enabled:
            return MemoryContext()

        start = time.monotonic()
        query_embedding = await self._embedder.embed(query)
        relevant = await self._store.search_similar(
            org_id=org_id,
            session_id=session_id,
            query_embedding=query_embedding,
            limit=self._settings.memory_retrieval_top_k,
            min_similarity=self._settings.memory_similarity_threshold,
        )
        summary = await self._store.get_summary(session_id)
        memory_retrieval_latency_seconds.observe(time.monotonic() - start)

        return MemoryContext(
            summary=summary,
            relevant_entries=relevant,
            recent_message_count=0,
        )

    async def build_messages_for_llm(
        self,
        *,
        org_id: UUID | None,
        session_id: UUID,
        system_prompt: str,
        recent_messages: list[ChatMessageLike],
        query: str,
    ) -> list[ChatMessageLike]:
        if not self._settings.memory_enabled or org_id is None:
            return recent_messages

        memory_context = await self.retrieve_context(
            org_id=org_id,
            session_id=session_id,
            query=query,
        )
        memory_context.recent_message_count = len(recent_messages)

        return self._context_builder.build(
            system_prompt=system_prompt,
            recent_messages=recent_messages,
            memory_context=memory_context,
            max_recent_messages=self._settings.memory_max_recent_messages,
        )

    async def list_entries(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ):
        return await self._store.list_entries(
            org_id=org_id,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )

    async def search(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        query: str,
        limit: int | None = None,
    ):
        query_embedding = await self._embedder.embed(query)
        return await self._store.search_similar(
            org_id=org_id,
            session_id=session_id,
            query_embedding=query_embedding,
            limit=limit or self._settings.memory_retrieval_top_k,
            min_similarity=self._settings.memory_similarity_threshold,
        )

    async def _maybe_summarize(self, org_id: UUID, session_id: UUID) -> None:
        if not self._summarizer:
            return

        turn_count = await self._store.count_turns(session_id)
        if turn_count < self._settings.memory_summarize_after_messages:
            return

        entries = await self._store.list_entries(
            org_id=org_id,
            session_id=session_id,
            limit=turn_count,
        )
        conversation = "\n".join(
            f"{entry.role}: {entry.content}"
            for entry in reversed(entries)
            if entry.entry_type == MemoryEntryType.TURN
        )
        summary = await self._summarizer.summarize(conversation)
        await self._store.upsert_summary(
            org_id=org_id,
            session_id=session_id,
            summary=summary,
            message_count=turn_count,
        )

        embedding = await self._embedder.embed(summary)
        await self._store.store_entry(
            org_id=org_id,
            session_id=session_id,
            role="system",
            content=summary,
            entry_type=MemoryEntryType.SUMMARY,
            embedding=embedding,
        )
