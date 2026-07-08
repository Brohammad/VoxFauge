from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardOverview(BaseModel):
    total_sessions: int = 0
    active_sessions: int = 0
    completed_sessions: int = 0
    total_messages: int = 0
    total_tool_calls: int = 0
    total_evaluations: int = 0
    avg_e2e_latency_ms: float | None = None
    avg_evaluation_score: float | None = None
    failed_evaluations: int = 0
    estimated_total_cost_usd: float | None = None


class SessionSummaryItem(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    ended_at: datetime | None
    message_count: int
    avg_e2e_ms: float | None = None
    last_evaluation_score: float | None = None


class LatencyBucket(BaseModel):
    metric_name: str
    avg_ms: float
    p95_ms: float | None = None
    sample_count: int


class EvaluationSummary(BaseModel):
    total_runs: int
    avg_score: float | None
    passed: int
    warning: int
    failed: int
    by_metric: dict[str, float] = Field(default_factory=dict)


class ActivityItem(BaseModel):
    type: str  # session | message | tool_call | evaluation
    timestamp: datetime
    session_id: UUID | None = None
    summary: str
    status: str | None = None


class OutcomeSummary(BaseModel):
    total_sessions: int = 0
    task_success_rate: float = 0.0
    escalation_rate: float = 0.0
    avg_resolution_time_seconds: float = 0.0
    top_intents: list[str] = Field(default_factory=list)
