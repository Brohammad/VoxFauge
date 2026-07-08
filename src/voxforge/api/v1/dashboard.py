from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from voxforge.api.dependencies import get_dashboard_service, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.dashboard import (
    ActivityItem,
    DashboardOverview,
    SessionSummaryItem,
)
from voxforge.modules.dashboard.application.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class OverviewResponse(BaseModel):
    total_sessions: int
    active_sessions: int
    completed_sessions: int
    total_messages: int
    total_tool_calls: int
    total_evaluations: int
    avg_e2e_latency_ms: float | None
    avg_evaluation_score: float | None
    failed_evaluations: int
    estimated_total_cost_usd: float | None


class SessionSummaryResponse(BaseModel):
    id: UUID
    status: str
    started_at: str
    ended_at: str | None
    message_count: int
    avg_e2e_ms: float | None
    last_evaluation_score: float | None


class LatencyBucketResponse(BaseModel):
    metric_name: str
    avg_ms: float
    p95_ms: float | None
    sample_count: int


class EvaluationSummaryResponse(BaseModel):
    total_runs: int
    avg_score: float | None
    passed: int
    warning: int
    failed: int
    by_metric: dict[str, float]


class ActivityItemResponse(BaseModel):
    type: str
    timestamp: str
    session_id: UUID | None
    summary: str
    status: str | None


class OutcomeSummaryResponse(BaseModel):
    total_sessions: int
    task_success_rate: float
    escalation_rate: float
    avg_resolution_time_seconds: float
    top_intents: list[str]


@router.get("/overview", response_model=OverviewResponse)
async def dashboard_overview(
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> OverviewResponse:
    overview = await dashboard.get_overview(principal.org_id)
    return _overview_response(overview)


@router.get("/sessions", response_model=list[SessionSummaryResponse])
async def dashboard_sessions(
    limit: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> list[SessionSummaryResponse]:
    sessions = await dashboard.get_recent_sessions(principal.org_id, limit=limit)
    return [_session_response(s) for s in sessions]


@router.get("/latency", response_model=list[LatencyBucketResponse])
async def dashboard_latency(
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> list[LatencyBucketResponse]:
    buckets = await dashboard.get_latency_stats(principal.org_id)
    return [
        LatencyBucketResponse(
            metric_name=b.metric_name,
            avg_ms=b.avg_ms,
            p95_ms=b.p95_ms,
            sample_count=b.sample_count,
        )
        for b in buckets
    ]


@router.get("/evaluations", response_model=EvaluationSummaryResponse)
async def dashboard_evaluations(
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> EvaluationSummaryResponse:
    summary = await dashboard.get_evaluation_summary(principal.org_id)
    return EvaluationSummaryResponse(
        total_runs=summary.total_runs,
        avg_score=summary.avg_score,
        passed=summary.passed,
        warning=summary.warning,
        failed=summary.failed,
        by_metric=summary.by_metric,
    )


@router.get("/activity", response_model=list[ActivityItemResponse])
async def dashboard_activity(
    limit: int = Query(30, ge=1, le=100),
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> list[ActivityItemResponse]:
    items = await dashboard.get_recent_activity(principal.org_id, limit=limit)
    return [_activity_response(i) for i in items]


@router.get("/outcomes", response_model=OutcomeSummaryResponse)
async def dashboard_outcomes(
    principal: Principal = Depends(require_scope("sessions:read")),
    dashboard: DashboardService = Depends(get_dashboard_service),
) -> OutcomeSummaryResponse:
    outcome = await dashboard.get_outcome_summary(principal.org_id)
    return OutcomeSummaryResponse(
        total_sessions=outcome.total_sessions,
        task_success_rate=outcome.task_success_rate,
        escalation_rate=outcome.escalation_rate,
        avg_resolution_time_seconds=outcome.avg_resolution_time_seconds,
        top_intents=outcome.top_intents,
    )


def _overview_response(o: DashboardOverview) -> OverviewResponse:
    return OverviewResponse(
        total_sessions=o.total_sessions,
        active_sessions=o.active_sessions,
        completed_sessions=o.completed_sessions,
        total_messages=o.total_messages,
        total_tool_calls=o.total_tool_calls,
        total_evaluations=o.total_evaluations,
        avg_e2e_latency_ms=o.avg_e2e_latency_ms,
        avg_evaluation_score=o.avg_evaluation_score,
        failed_evaluations=o.failed_evaluations,
        estimated_total_cost_usd=o.estimated_total_cost_usd,
    )


def _session_response(s: SessionSummaryItem) -> SessionSummaryResponse:
    return SessionSummaryResponse(
        id=s.id,
        status=s.status,
        started_at=s.started_at.isoformat(),
        ended_at=s.ended_at.isoformat() if s.ended_at else None,
        message_count=s.message_count,
        avg_e2e_ms=s.avg_e2e_ms,
        last_evaluation_score=s.last_evaluation_score,
    )


def _activity_response(i: ActivityItem) -> ActivityItemResponse:
    return ActivityItemResponse(
        type=i.type,
        timestamp=i.timestamp.isoformat(),
        session_id=i.session_id,
        summary=i.summary,
        status=i.status,
    )
