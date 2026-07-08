from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SessionReplayEvent(BaseModel):
    event_type: str  # message | tool_call | evaluation | outcome | metric
    timestamp: datetime
    summary: str
    status: str | None = None
    role: str | None = None
    payload: dict = Field(default_factory=dict)


class SessionOutcomeSummary(BaseModel):
    intent: str
    task_success: bool
    escalation: bool
    resolution_time_seconds: float
    recorded_at: datetime


class ExplainabilityItem(BaseModel):
    kind: str  # safety | critic | tool | outcome
    decision: str
    reason: str


class SessionReplay(BaseModel):
    session_id: UUID
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    transport_type: str
    metadata: dict = Field(default_factory=dict)
    outcome: SessionOutcomeSummary | None = None
    explanations: list[ExplainabilityItem] = Field(default_factory=list)
    events: list[SessionReplayEvent] = Field(default_factory=list)
