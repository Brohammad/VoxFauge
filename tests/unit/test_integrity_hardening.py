"""Unit and concurrency tests for P1 Group 2 integrity hardening."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.core.domain.entities import SessionStatus
from voxforge.core.domain.handoff import HandoffStatus, HandoffTrigger
from voxforge.core.domain.support import TicketCreateRequest
from voxforge.core.events.bus import EventBus
from voxforge.core.exceptions import SessionStateError
from voxforge.infrastructure.db.handoff_repository import HandoffRepository
from voxforge.infrastructure.db.models import OutcomeKPIModel
from voxforge.infrastructure.db.outcome_repository import OutcomeRepository
from voxforge.infrastructure.providers.support.mock import MockTicketingProvider
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.session_manager.application.service import SessionManager


@pytest.mark.asyncio
async def test_handoff_create_handles_integrity_error(db_session):
    org_id = uuid4()
    session_id = uuid4()
    repo = HandoffRepository(db_session)

    first, created_first = await repo.create_handoff(
        org_id=org_id,
        session_id=session_id,
        trigger=HandoffTrigger.USER_REQUEST,
        trigger_reason="first",
    )
    assert created_first is True

    second, created_second = await repo.create_handoff(
        org_id=org_id,
        session_id=session_id,
        trigger=HandoffTrigger.USER_REQUEST,
        trigger_reason="second",
    )
    assert created_second is False
    assert second.id == first.id


@pytest.fixture
def settings():
    from voxforge.config import Settings

    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
    )


@pytest.mark.asyncio
async def test_concurrent_handoff_create_single_row(db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    org_id = uuid4()
    session_id = uuid4()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def create():
        async with factory() as session:
            repo = HandoffRepository(session)
            result = await repo.create_handoff(
                org_id=org_id,
                session_id=session_id,
                trigger=HandoffTrigger.POLICY,
                trigger_reason="race",
            )
            await session.commit()
            return result

    results = await asyncio.gather(create(), create(), return_exceptions=True)
    created_ids = set()
    for result in results:
        if isinstance(result, Exception):
            pytest.fail(f"Unexpected exception: {result}")
        record, _created = result
        created_ids.add(record.id)

    assert len(created_ids) == 1


@pytest.mark.asyncio
async def test_outcome_upsert_idempotent(db_session):
    org_id = uuid4()
    session_id = uuid4()
    repo = OutcomeRepository(db_session)

    _, created_first = await repo.upsert_session_outcome(
        org_id=org_id,
        session_id=session_id,
        intent="billing_support",
        task_success=True,
        escalation=False,
        resolution_time_seconds=12.0,
    )
    _, created_second = await repo.upsert_session_outcome(
        org_id=org_id,
        session_id=session_id,
        intent="billing_support",
        task_success=False,
        escalation=True,
        resolution_time_seconds=24.0,
    )

    assert created_first is True
    assert created_second is False

    from sqlalchemy import select

    result = await db_session.execute(
        select(OutcomeKPIModel).where(OutcomeKPIModel.session_id == session_id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].escalation is True
    assert rows[0].resolution_time_seconds == 24.0


@pytest.mark.asyncio
async def test_concurrent_outcome_upsert_single_row(db_engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    org_id = uuid4()
    session_id = uuid4()
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def upsert(task_success: bool):
        async with factory() as session:
            repo = OutcomeRepository(session)
            result = await repo.upsert_session_outcome(
                org_id=org_id,
                session_id=session_id,
                intent="general_support",
                task_success=task_success,
                escalation=False,
                resolution_time_seconds=5.0,
            )
            await session.commit()
            return result

    await asyncio.gather(upsert(True), upsert(False))

    async with factory() as session:
        from sqlalchemy import func, select

        result = await session.execute(
            select(func.count())
            .select_from(OutcomeKPIModel)
            .where(OutcomeKPIModel.session_id == session_id)
        )
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_mock_ticketing_session_idempotent():
    provider = MockTicketingProvider()
    request = TicketCreateRequest(
        subject="Test",
        description="Issue",
        session_id="sess-123",
    )
    first = await provider.create_ticket(request)
    second = await provider.create_ticket(request)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_activate_session_idempotent(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session()
    first = await manager.activate_session(session.id)
    second = await manager.activate_session(session.id)

    assert first.status == SessionStatus.ACTIVE
    assert second.status == SessionStatus.ACTIVE


@pytest.mark.asyncio
async def test_resume_rejects_terminal_session(db_session, fake_redis, settings):
    store = RedisSessionStateStore(fake_redis)
    manager = SessionManager(db_session, store, EventBus(), settings)

    session = await manager.create_session()
    await manager.end_session(session.id)
    await db_session.commit()

    with pytest.raises(SessionStateError, match="terminal"):
        await manager.resume_session(session.id)


@pytest.mark.asyncio
async def test_handoff_update_status_guard(db_session):
    org_id = uuid4()
    session_id = uuid4()
    repo = HandoffRepository(db_session)
    record, _ = await repo.create_handoff(
        org_id=org_id,
        session_id=session_id,
        trigger=HandoffTrigger.USER_REQUEST,
        trigger_reason="guard test",
    )

    updated = await repo.update_status(
        record.id,
        org_id=org_id,
        status=HandoffStatus.COMPLETED.value,
        allowed_from=frozenset({HandoffStatus.PENDING.value}),
        completed_at=datetime.now(UTC),
    )
    assert updated is not None
    assert updated.status == HandoffStatus.COMPLETED

    blocked = await repo.update_status(
        record.id,
        org_id=org_id,
        status=HandoffStatus.ACTIVE.value,
        allowed_from=frozenset({HandoffStatus.PENDING.value}),
    )
    assert blocked is None


@pytest.mark.asyncio
async def test_handoff_snapshot_deduplicated(db_session):
    org_id = uuid4()
    session_id = uuid4()
    repo = HandoffRepository(db_session)
    record, _ = await repo.create_handoff(
        org_id=org_id,
        session_id=session_id,
        trigger=HandoffTrigger.USER_REQUEST,
        trigger_reason="snapshot",
    )

    first = await repo.save_snapshot(
        handoff_id=record.id,
        session_id=session_id,
        org_id=org_id,
        message_count=1,
        snapshot={"messages": []},
    )
    second = await repo.save_snapshot(
        handoff_id=record.id,
        session_id=session_id,
        org_id=org_id,
        message_count=2,
        snapshot={"messages": [{"id": "1"}]},
    )
    assert first.id == second.id
