from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from voxforge.api.dependencies import get_replay_service, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.replay import (
    ExplainabilityItem,
    SessionOutcomeSummary,
    SessionReplay,
    SessionReplayEvent,
)
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.modules.replay.application.service import ReplayService

router = APIRouter(prefix="/sessions", tags=["replay"])


class ReplayEventResponse(BaseModel):
    event_type: str
    timestamp: str
    summary: str
    status: str | None = None
    role: str | None = None
    payload: dict = Field(default_factory=dict)


class OutcomeSummaryResponse(BaseModel):
    intent: str
    task_success: bool
    escalation: bool
    resolution_time_seconds: float
    recorded_at: str


class ExplainabilityItemResponse(BaseModel):
    kind: str
    decision: str
    reason: str


class SessionReplayResponse(BaseModel):
    session_id: UUID
    status: str
    started_at: str
    ended_at: str | None = None
    transport_type: str
    metadata: dict
    outcome: OutcomeSummaryResponse | None = None
    explanations: list[ExplainabilityItemResponse] = Field(default_factory=list)
    events: list[ReplayEventResponse]


@router.get("/{session_id}/replay", response_model=SessionReplayResponse)
async def get_session_replay(
    session_id: UUID,
    principal: Principal = Depends(require_scope("sessions:read")),
    replay_service: ReplayService = Depends(get_replay_service),
) -> SessionReplayResponse:
    try:
        replay = await replay_service.get_session_replay(session_id, org_id=principal.org_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _to_response(replay)


def _to_response(replay: SessionReplay) -> SessionReplayResponse:
    return SessionReplayResponse(
        session_id=replay.session_id,
        status=replay.status,
        started_at=_iso(replay.started_at),
        ended_at=_iso(replay.ended_at) if replay.ended_at else None,
        transport_type=replay.transport_type,
        metadata=replay.metadata,
        outcome=_outcome_response(replay.outcome) if replay.outcome else None,
        explanations=[_explanation_response(item) for item in replay.explanations],
        events=[_event_response(event) for event in replay.events],
    )


def _outcome_response(outcome: SessionOutcomeSummary) -> OutcomeSummaryResponse:
    return OutcomeSummaryResponse(
        intent=outcome.intent,
        task_success=outcome.task_success,
        escalation=outcome.escalation,
        resolution_time_seconds=outcome.resolution_time_seconds,
        recorded_at=_iso(outcome.recorded_at),
    )


def _explanation_response(item: ExplainabilityItem) -> ExplainabilityItemResponse:
    return ExplainabilityItemResponse(
        kind=item.kind,
        decision=item.decision,
        reason=item.reason,
    )


def _event_response(event: SessionReplayEvent) -> ReplayEventResponse:
    return ReplayEventResponse(
        event_type=event.event_type,
        timestamp=_iso(event.timestamp),
        summary=event.summary,
        status=event.status,
        role=event.role,
        payload=event.payload,
    )


def _iso(value: datetime) -> str:
    return value.isoformat()
