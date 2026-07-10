"""REST API for human handoff management."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_handoff_orchestrator, get_session_manager, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.handoff import HandoffEventType, HandoffStatus, HandoffTrigger
from voxforge.infrastructure.db.handoff_repository import HandoffRepository
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.observability.metrics import (
    duplicate_suppressed_total,
    handoff_completed_total,
)
from voxforge.modules.handoff.application.orchestrator import HandoffOrchestrator
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(prefix="/handoffs", tags=["handoffs"])


class HandoffResponse(BaseModel):
    id: UUID
    session_id: UUID
    status: str
    trigger: str
    trigger_reason: str
    ticket_id: str | None = None
    conversation_summary: str | None = None
    replay_url: str | None = None
    assigned_to_user_id: UUID | None = None
    assigned_to_email: str | None = None
    confidence_score: float | None = None


class InitiateHandoffRequest(BaseModel):
    trigger: HandoffTrigger = HandoffTrigger.USER_REQUEST
    reason: str = ""
    priority: str = "normal"
    customer_email: str | None = None


class HandoffContextResponse(BaseModel):
    handoff_id: UUID
    session_id: UUID
    conversation_summary: str | None = None
    replay_url: str | None = None
    ticket: dict | None = None
    recent_messages: list[dict] = Field(default_factory=list)
    status: str


class CompleteHandoffRequest(BaseModel):
    resolution: str = "resolved"


def _to_response(record) -> HandoffResponse:
    return HandoffResponse(
        id=record.id,
        session_id=record.session_id,
        status=record.status.value if hasattr(record.status, "value") else str(record.status),
        trigger=record.trigger.value if hasattr(record.trigger, "value") else str(record.trigger),
        trigger_reason=record.trigger_reason,
        ticket_id=record.ticket_id,
        conversation_summary=record.conversation_summary,
        replay_url=record.replay_url,
        assigned_to_user_id=record.assigned_to_user_id,
        assigned_to_email=record.assigned_to_email,
        confidence_score=record.confidence_score,
    )


@router.get("", response_model=list[HandoffResponse])
async def list_handoffs(
    status: str | None = Query(None),
    principal: Principal = Depends(require_scope("handoffs:read")),
    db: AsyncSession = Depends(get_db_session),
) -> list[HandoffResponse]:
    repo = HandoffRepository(db)
    records = await repo.list_handoffs(org_id=principal.org_id, status=status)
    return [_to_response(r) for r in records]


@router.get("/{handoff_id}", response_model=HandoffResponse)
async def get_handoff(
    handoff_id: UUID,
    principal: Principal = Depends(require_scope("handoffs:read")),
    db: AsyncSession = Depends(get_db_session),
) -> HandoffResponse:
    repo = HandoffRepository(db)
    record = await repo.get_handoff(handoff_id, org_id=principal.org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return _to_response(record)


@router.get("/{handoff_id}/context", response_model=HandoffContextResponse)
async def get_handoff_context(
    handoff_id: UUID,
    principal: Principal = Depends(require_scope("handoffs:read")),
    db: AsyncSession = Depends(get_db_session),
    session_manager: SessionManager = Depends(get_session_manager),
) -> HandoffContextResponse:
    repo = HandoffRepository(db)
    record = await repo.get_handoff(handoff_id, org_id=principal.org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Handoff not found")

    messages = await session_manager.get_messages(record.session_id, limit=20)
    ticket = None
    if record.ticket_id:
        ticket = {"id": record.ticket_id, "provider": record.ticket_provider}

    return HandoffContextResponse(
        handoff_id=record.id,
        session_id=record.session_id,
        conversation_summary=record.conversation_summary,
        replay_url=record.replay_url,
        ticket=ticket,
        recent_messages=[
            {
                "id": str(m.id),
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        status=record.status.value if hasattr(record.status, "value") else str(record.status),
    )


@router.post("/{handoff_id}/accept", response_model=HandoffResponse)
async def accept_handoff(
    handoff_id: UUID,
    principal: Principal = Depends(require_scope("handoffs:write")),
    orchestrator: HandoffOrchestrator = Depends(get_handoff_orchestrator),
    db: AsyncSession = Depends(get_db_session),
) -> HandoffResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=403, detail="User context required")
    try:
        record = await orchestrator.accept_handoff(
            handoff_id=handoff_id,
            org_id=principal.org_id,
            user_id=principal.user_id,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already" in detail.lower() or " is " in detail.lower() else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return _to_response(record)


@router.post("/{handoff_id}/complete", response_model=HandoffResponse)
async def complete_handoff(
    handoff_id: UUID,
    body: CompleteHandoffRequest,
    principal: Principal = Depends(require_scope("handoffs:write")),
    orchestrator: HandoffOrchestrator = Depends(get_handoff_orchestrator),
    db: AsyncSession = Depends(get_db_session),
) -> HandoffResponse:
    try:
        record = await orchestrator.complete_handoff(
            handoff_id=handoff_id,
            org_id=principal.org_id,
            resolution=body.resolution,
        )
        await db.commit()
    except ValueError as exc:
        detail = str(exc)
        status_code = 409 if "already" in detail.lower() or "is " in detail.lower() else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return _to_response(record)


_CANCELABLE = frozenset(
    {HandoffStatus.PENDING.value, HandoffStatus.ASSIGNED.value, HandoffStatus.ACTIVE.value}
)


@router.post("/{handoff_id}/cancel", response_model=HandoffResponse)
async def cancel_handoff(
    handoff_id: UUID,
    principal: Principal = Depends(require_scope("handoffs:write")),
    db: AsyncSession = Depends(get_db_session),
    session_manager: SessionManager = Depends(get_session_manager),
) -> HandoffResponse:
    repo = HandoffRepository(db)
    record = await repo.get_handoff(handoff_id, org_id=principal.org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Handoff not found")

    if record.status == HandoffStatus.CANCELLED:
        duplicate_suppressed_total.labels(resource="handoff_cancel").inc()
        return _to_response(record)
    if record.status == HandoffStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Handoff is completed")

    updated = await repo.update_status(
        handoff_id,
        org_id=principal.org_id,
        status=HandoffStatus.CANCELLED.value,
        allowed_from=_CANCELABLE,
    )
    if updated is None:
        record = await repo.get_handoff(handoff_id, org_id=principal.org_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Handoff not found")
        if record.status == HandoffStatus.CANCELLED:
            duplicate_suppressed_total.labels(resource="handoff_cancel").inc()
            return _to_response(record)
        raise HTTPException(status_code=409, detail=f"Handoff is {record.status.value}")

    record = updated
    await repo.record_event(
        handoff_id,
        org_id=principal.org_id,
        event_type=HandoffEventType.CANCELLED.value,
        payload={},
    )
    await repo.link_session(
        session_id=record.session_id,
        handoff_id=handoff_id,
        handoff_status=HandoffStatus.CANCELLED.value,
    )
    await session_manager.clear_handoff(record.session_id)
    handoff_completed_total.labels(status=HandoffStatus.CANCELLED.value).inc()
    await db.commit()
    return _to_response(record)
