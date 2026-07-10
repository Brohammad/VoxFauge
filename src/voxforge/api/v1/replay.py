import hmac
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from voxforge.api.dependencies import (
    get_handoff_repository,
    get_optional_principal,
    get_replay_service,
    get_settings,
    rate_limit_category_optional,
)
from voxforge.config import Settings
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.replay import (
    ExplainabilityItem,
    SessionOutcomeSummary,
    SessionReplay,
    SessionReplayEvent,
)
from voxforge.core.exceptions import ForbiddenError, SessionNotFoundError
from voxforge.infrastructure.db.handoff_repository import HandoffRepository
from voxforge.modules.auth.application.service import AuthService
from voxforge.modules.handoff.application.replay_link import ReplayLinkService
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
    replay_token: str | None = Query(default=None),
    _: None = Depends(rate_limit_category_optional("replay")),
    principal: Principal | None = Depends(get_optional_principal),
    settings: Settings = Depends(get_settings),
    replay_service: ReplayService = Depends(get_replay_service),
    handoff_repo: HandoffRepository = Depends(get_handoff_repository),
) -> SessionReplayResponse:
    org_id = await _resolve_replay_org_id(
        session_id=session_id,
        replay_token=replay_token,
        principal=principal,
        settings=settings,
        handoff_repo=handoff_repo,
    )
    try:
        replay = await replay_service.get_session_replay(session_id, org_id=org_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _to_response(replay)


async def _resolve_replay_org_id(
    *,
    session_id: UUID,
    replay_token: str | None,
    principal: Principal | None,
    settings: Settings,
    handoff_repo: HandoffRepository,
) -> UUID:
    if replay_token:
        handoff = await handoff_repo.get_handoff_by_session(session_id)
        if handoff is None:
            raise HTTPException(status_code=404, detail="Handoff not found for session")
        link_service = ReplayLinkService(settings)
        if not link_service.verify(
            session_id=session_id,
            org_id=handoff.org_id,
            handoff_id=handoff.id,
            token=replay_token,
        ):
            raise HTTPException(status_code=403, detail="Invalid replay token")
        if handoff.replay_token and not hmac.compare_digest(handoff.replay_token, replay_token):
            raise HTTPException(status_code=403, detail="Invalid replay token")
        age_seconds = (datetime.now(UTC) - handoff.created_at).total_seconds()
        if age_seconds > settings.handoff_replay_token_ttl_seconds:
            raise HTTPException(status_code=403, detail="Replay token expired")
        return handoff.org_id

    if principal is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        AuthService.require_scope(principal, "sessions:read")
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return principal.org_id


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
