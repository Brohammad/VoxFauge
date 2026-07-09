import math
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.memory import MemoryEntry, MemoryEntryType
from voxforge.infrastructure.db.models import MemoryEntryModel, SessionSummaryModel


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _pgvector_literal(embedding: list[float]) -> str:
    """Format a float list for PostgreSQL pgvector CAST(... AS vector)."""
    return "[" + ",".join(str(v) for v in embedding) + "]"


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> MemoryEntry:
        entry_id = uuid4()
        model = MemoryEntryModel(
            id=entry_id,
            org_id=org_id,
            session_id=session_id,
            message_id=message_id,
            role=role,
            content=content,
            entry_type=entry_type.value,
            embedding=embedding,
            metadata_=metadata or {},
        )
        self._session.add(model)
        await self._session.flush()

        dialect = self._session.bind.dialect.name if self._session.bind else ""
        if dialect == "postgresql" and embedding:
            await self._session.execute(
                text(
                    "UPDATE memory_entries SET embedding_vec = CAST(:vec AS vector) "
                    "WHERE id = :id"
                ),
                {"vec": _pgvector_literal(embedding), "id": str(entry_id)},
            )

        return self._to_entry(model)

    async def search_similar(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        query_embedding: list[float],
        limit: int,
        min_similarity: float,
    ) -> list[MemoryEntry]:
        dialect = self._session.bind.dialect.name if self._session.bind else ""

        if dialect == "postgresql":
            query_vec = _pgvector_literal(query_embedding)
            result = await self._session.execute(
                text(
                    """
                    SELECT id, org_id, session_id, message_id, role, content,
                           entry_type, metadata, created_at,
                           1 - (embedding_vec <=> CAST(:query_vec AS vector)) AS similarity
                    FROM memory_entries
                    WHERE org_id = :org_id
                      AND session_id = :session_id
                      AND embedding_vec IS NOT NULL
                      AND entry_type = 'turn'
                    ORDER BY embedding_vec <=> CAST(:query_vec AS vector)
                    LIMIT :limit
                    """
                ),
                {
                    "org_id": str(org_id),
                    "session_id": str(session_id),
                    "query_vec": query_vec,
                    "limit": limit,
                },
            )
            entries = []
            for row in result.mappings():
                similarity = float(row["similarity"])
                if similarity < min_similarity:
                    continue
                entries.append(
                    MemoryEntry(
                        id=row["id"],
                        org_id=row["org_id"],
                        session_id=row["session_id"],
                        role=row["role"],
                        content=row["content"],
                        entry_type=MemoryEntryType(row["entry_type"]),
                        message_id=row["message_id"],
                        metadata=row["metadata"] or {},
                        similarity=similarity,
                        created_at=row["created_at"],
                    )
                )
            return entries

        return await self._search_similar_in_memory(
            org_id=org_id,
            session_id=session_id,
            query_embedding=query_embedding,
            limit=limit,
            min_similarity=min_similarity,
        )

    async def _search_similar_in_memory(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        query_embedding: list[float],
        limit: int,
        min_similarity: float,
    ) -> list[MemoryEntry]:
        result = await self._session.execute(
            select(MemoryEntryModel).where(
                MemoryEntryModel.org_id == org_id,
                MemoryEntryModel.session_id == session_id,
                MemoryEntryModel.entry_type == MemoryEntryType.TURN.value,
                MemoryEntryModel.embedding.is_not(None),
            )
        )
        scored: list[tuple[float, MemoryEntryModel]] = []
        for model in result.scalars():
            similarity = _cosine_similarity(query_embedding, model.embedding or [])
            if similarity >= min_similarity:
                scored.append((similarity, model))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            self._to_entry(model, similarity=score) for score, model in scored[:limit]
        ]

    async def list_entries(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryEntry]:
        result = await self._session.execute(
            select(MemoryEntryModel)
            .where(
                MemoryEntryModel.org_id == org_id,
                MemoryEntryModel.session_id == session_id,
            )
            .order_by(MemoryEntryModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_entry(model) for model in result.scalars()]

    async def get_summary(self, session_id: UUID) -> str | None:
        result = await self._session.execute(
            select(SessionSummaryModel).where(SessionSummaryModel.session_id == session_id)
        )
        model = result.scalar_one_or_none()
        return model.summary if model else None

    async def upsert_summary(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        summary: str,
        message_count: int,
    ) -> None:
        from datetime import UTC, datetime

        result = await self._session.execute(
            select(SessionSummaryModel).where(SessionSummaryModel.session_id == session_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.summary = summary
            existing.message_count = message_count
            existing.updated_at = datetime.now(UTC)
        else:
            self._session.add(
                SessionSummaryModel(
                    org_id=org_id,
                    session_id=session_id,
                    summary=summary,
                    message_count=message_count,
                )
            )
        await self._session.flush()

    async def count_turns(self, session_id: UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(MemoryEntryModel)
            .where(
                MemoryEntryModel.session_id == session_id,
                MemoryEntryModel.entry_type == MemoryEntryType.TURN.value,
            )
        )
        return int(result.scalar_one())

    @staticmethod
    def _to_entry(model: MemoryEntryModel, *, similarity: float | None = None) -> MemoryEntry:
        return MemoryEntry(
            id=model.id,
            org_id=model.org_id,
            session_id=model.session_id,
            role=model.role,
            content=model.content,
            entry_type=MemoryEntryType(model.entry_type),
            message_id=model.message_id,
            metadata=model.metadata_,
            similarity=similarity,
            created_at=model.created_at,
        )
