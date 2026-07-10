"""Domain models for enterprise human handoff."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class HandoffTrigger(StrEnum):
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    TOOL_FAILURE = "tool_failure"
    USER_REQUEST = "user_request"
    POLICY = "policy"
    AGENT_EXPLICIT = "agent_explicit"


class HandoffStatus(StrEnum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class HandoffEventType(StrEnum):
    CREATED = "created"
    TICKET_CREATED = "ticket_created"
    SUMMARY_GENERATED = "summary_generated"
    REPLAY_LINKED = "replay_linked"
    ASSIGNED = "assigned"
    ACCEPTED = "accepted"
    RESUMED = "resumed"
    MESSAGE = "message"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentStrategy(StrEnum):
    ROUND_ROBIN = "round_robin"
    MANUAL = "manual"
    LEAST_LOADED = "least_loaded"


class EscalationPolicy(BaseModel):
    """Org-level escalation policy from agent config or support template."""

    fallback_to_human: bool = True
    min_confidence: float = 0.55
    escalate_on_tool_failure: bool = True
    max_tool_failures: int = 2
    escalate_on_critical_tool_failure: bool = True
    require_explicit_request: bool = False
    auto_create_ticket: bool = True
    assignment_strategy: AssignmentStrategy = AssignmentStrategy.ROUND_ROBIN
    handoff_message: str = (
        "I'm connecting you with a specialist who can help further. "
        "Please hold while I transfer your conversation."
    )


class ConfidenceSignals(BaseModel):
    """Per-turn signals that compose the handoff confidence score."""

    critic_approved: bool | None = None
    hallucination_score: float | None = None
    tool_success_ratio: float | None = None
    stt_confidence: float | None = None
    kb_top_similarity: float | None = None


class TurnHandoffContext(BaseModel):
    """Input to HandoffPolicyEngine.evaluate()."""

    user_transcript: str
    assistant_response: str = ""
    interrupted: bool = False
    confidence_signals: ConfidenceSignals = Field(default_factory=ConfidenceSignals)
    tool_failures_this_turn: int = 0
    consecutive_tool_failures: int = 0
    failed_tools: list[str] = Field(default_factory=list)
    critical_tool_failed: bool = False


class HandoffDecision(BaseModel):
    """Output of policy evaluation."""

    should_escalate: bool
    trigger: HandoffTrigger | None = None
    confidence: float | None = None
    reason: str = ""


class HandoffRecord(BaseModel):
    id: UUID
    org_id: UUID
    session_id: UUID
    ticket_id: str | None = None
    ticket_provider: str = "mock"
    status: HandoffStatus = HandoffStatus.PENDING
    trigger: HandoffTrigger
    trigger_reason: str = ""
    confidence_score: float | None = None
    conversation_summary: str | None = None
    replay_url: str | None = None
    replay_token: str | None = None
    assigned_to_user_id: UUID | None = None
    assigned_to_email: str | None = None
    assigned_at: datetime | None = None
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HandoffAssignment(BaseModel):
    handoff_id: UUID
    assignee_user_id: UUID | None = None
    assignee_email: str | None = None
    strategy: AssignmentStrategy
    queue_position: int | None = None


class HandoffPackage(BaseModel):
    """Complete handoff payload returned to agent and human."""

    handoff_id: UUID
    session_id: UUID
    ticket_id: str | None = None
    conversation_summary: str
    replay_url: str
    assignment: HandoffAssignment | None = None
    handoff_message: str
    trigger: HandoffTrigger
    confidence_score: float | None = None


class ConversationSnapshot(BaseModel):
    id: UUID
    handoff_id: UUID
    session_id: UUID
    org_id: UUID
    message_count: int
    snapshot: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}
