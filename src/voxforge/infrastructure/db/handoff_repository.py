"""PostgreSQL persistence for human handoff records and events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.handoff import (
    ConversationSnapshot,
    HandoffEventType,
    HandoffRecord,
    HandoffStatus,
    HandoffTrigger,
)
from voxforge.infrastructure.db.models import (
    ConversationSnapshotModel,
    HandoffEventModel,
    HandoffRecordModel,
    VoiceSessionModel,
)
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    duplicate_suppressed_total,
    integrity_violations_total,
)

logger = get_logger(__name__)


class HandoffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_handoff(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        trigger: HandoffTrigger,
        trigger_reason: str,
        confidence_score: float | None = None,
        metadata: dict | None = None,
    ) -> tuple[HandoffRecord, bool]:
        existing = await self.get_by_session(session_id, org_id=org_id)
        if existing is not None:
            return existing, False

        now = datetime.now(UTC)
        handoff_id = uuid4()
        values = {
            "id": handoff_id,
            "org_id": org_id,
            "session_id": session_id,
            "trigger": trigger.value,
            "trigger_reason": trigger_reason,
            "confidence_score": confidence_score,
            "status": HandoffStatus.PENDING.value,
            "metadata_": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        dialect = self._session.bind.dialect.name if self._session.bind else ""
        if dialect == "postgresql":
            stmt = (
                pg_insert(HandoffRecordModel)
                .values(values)
                .on_conflict_do_nothing(constraint="uq_handoff_records_session")
                .returning(HandoffRecordModel.id)
            )
        else:
            stmt = (
                sqlite_insert(HandoffRecordModel)
                .values(values)
                .on_conflict_do_nothing(index_elements=["session_id"])
                .returning(HandoffRecordModel.id)
            )

        result = await self._session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            integrity_violations_total.labels(resource="handoff", operation="create").inc()
            duplicate_suppressed_total.labels(resource="handoff").inc()
            logger.info(
                "handoff_create_duplicate_suppressed",
                session_id=str(session_id),
                org_id=str(org_id),
            )
            existing = await self.get_by_session(session_id, org_id=org_id)
            if existing is None:
                raise RuntimeError("handoff conflict without existing row")
            return existing, False

        await self.record_event(
            handoff_id,
            org_id=org_id,
            event_type=HandoffEventType.CREATED.value,
            payload={"trigger": trigger.value, "reason": trigger_reason},
        )
        record = await self.get_handoff(handoff_id, org_id=org_id)
        if record is None:
            raise RuntimeError("handoff not found after insert")
        return record, True

    async def get_by_session(
        self,
        session_id: UUID,
        *,
        org_id: UUID,
    ) -> HandoffRecord | None:
        result = await self._session.execute(
            select(HandoffRecordModel).where(
                HandoffRecordModel.session_id == session_id,
                HandoffRecordModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_record(model) if model else None

    async def get_handoff_by_session(self, session_id: UUID) -> HandoffRecord | None:
        result = await self._session.execute(
            select(HandoffRecordModel).where(HandoffRecordModel.session_id == session_id)
        )
        model = result.scalar_one_or_none()
        return self._to_record(model) if model else None

    async def get_handoff(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
    ) -> HandoffRecord | None:
        result = await self._session.execute(
            select(HandoffRecordModel).where(
                HandoffRecordModel.id == handoff_id,
                HandoffRecordModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_record(model) if model else None

    async def list_handoffs(
        self,
        *,
        org_id: UUID,
        status: str | None = None,
        limit: int = 50,
    ) -> list[HandoffRecord]:
        query = select(HandoffRecordModel).where(HandoffRecordModel.org_id == org_id)
        if status:
            query = query.where(HandoffRecordModel.status == status)
        query = query.order_by(HandoffRecordModel.created_at.desc()).limit(limit)
        result = await self._session.execute(query)
        return [self._to_record(m) for m in result.scalars().all()]

    async def update_status(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
        status: str,
        allowed_from: frozenset[str] | None = None,
        **fields: object,
    ) -> HandoffRecord | None:
        values: dict = {"status": status, "updated_at": datetime.now(UTC)}
        for key, value in fields.items():
            if key == "metadata":
                values["metadata_"] = value
            else:
                values[key] = value

        stmt = (
            update(HandoffRecordModel)
            .where(
                HandoffRecordModel.id == handoff_id,
                HandoffRecordModel.org_id == org_id,
            )
            .values(**values)
        )
        if allowed_from is not None:
            stmt = stmt.where(HandoffRecordModel.status.in_(allowed_from))

        result = await self._session.execute(stmt)
        await self._session.flush()
        if allowed_from is not None and result.rowcount == 0:
            return None
        record = await self.get_handoff(handoff_id, org_id=org_id)
        if record is None:
            raise ValueError("Handoff not found after update")
        return record

    async def link_session(
        self,
        *,
        session_id: UUID,
        handoff_id: UUID,
        handoff_status: str,
    ) -> None:
        await self._session.execute(
            update(VoiceSessionModel)
            .where(VoiceSessionModel.id == session_id)
            .values(handoff_id=handoff_id, handoff_status=handoff_status)
        )

    async def record_event(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
        event_type: str,
        payload: dict | None = None,
    ) -> None:
        self._session.add(
            HandoffEventModel(
                id=uuid4(),
                handoff_id=handoff_id,
                org_id=org_id,
                event_type=event_type,
                payload=payload or {},
                created_at=datetime.now(UTC),
            )
        )
        await self._session.flush()

    async def list_events(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
    ) -> list[HandoffEventModel]:
        result = await self._session.execute(
            select(HandoffEventModel)
            .where(
                HandoffEventModel.handoff_id == handoff_id,
                HandoffEventModel.org_id == org_id,
            )
            .order_by(HandoffEventModel.created_at.asc())
        )
        return list(result.scalars().all())

    async def save_snapshot(
        self,
        *,
        handoff_id: UUID,
        session_id: UUID,
        org_id: UUID,
        message_count: int,
        snapshot: dict,
    ) -> ConversationSnapshot:
        existing = await self._session.execute(
            select(ConversationSnapshotModel).where(
                ConversationSnapshotModel.handoff_id == handoff_id
            )
        )
        existing_model = existing.scalar_one_or_none()
        if existing_model is not None:
            duplicate_suppressed_total.labels(resource="handoff_snapshot").inc()
            return ConversationSnapshot(
                id=existing_model.id,
                handoff_id=existing_model.handoff_id,
                session_id=existing_model.session_id,
                org_id=existing_model.org_id,
                message_count=existing_model.message_count,
                snapshot=existing_model.snapshot,
                created_at=existing_model.created_at,
            )

        model = ConversationSnapshotModel(
            id=uuid4(),
            handoff_id=handoff_id,
            session_id=session_id,
            org_id=org_id,
            message_count=message_count,
            snapshot=snapshot,
            created_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()
        return ConversationSnapshot(
            id=model.id,
            handoff_id=model.handoff_id,
            session_id=model.session_id,
            org_id=model.org_id,
            message_count=model.message_count,
            snapshot=model.snapshot,
            created_at=model.created_at,
        )

    async def count_pending(self, *, org_id: UUID) -> int:
        result = await self._session.execute(
            select(HandoffRecordModel).where(
                HandoffRecordModel.org_id == org_id,
                HandoffRecordModel.status == HandoffStatus.PENDING.value,
            )
        )
        return len(result.scalars().all())

    @staticmethod
    def _to_record(model: HandoffRecordModel) -> HandoffRecord:
        return HandoffRecord(
            id=model.id,
            org_id=model.org_id,
            session_id=model.session_id,
            ticket_id=model.ticket_id,
            ticket_provider=model.ticket_provider,
            status=HandoffStatus(model.status),
            trigger=HandoffTrigger(model.trigger),
            trigger_reason=model.trigger_reason or "",
            confidence_score=model.confidence_score,
            conversation_summary=model.conversation_summary,
            replay_url=model.replay_url,
            replay_token=model.replay_token,
            assigned_to_user_id=model.assigned_to_user_id,
            assigned_to_email=model.assigned_to_email,
            assigned_at=model.assigned_at,
            accepted_at=model.accepted_at,
            completed_at=model.completed_at,
            metadata=model.metadata_ or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
