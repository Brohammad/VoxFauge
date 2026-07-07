from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionPhase(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TransportType(StrEnum):
    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"


class VoiceSession(BaseModel):
    id: UUID
    status: SessionStatus
    transport_type: TransportType = TransportType.WEBSOCKET
    org_id: UUID | None = None
    created_by_user_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None
    total_latency_ms: float | None = None

    model_config = {"from_attributes": True}


class Message(BaseModel):
    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    content_type: str = "text"
    provider_metadata: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionMetric(BaseModel):
    id: UUID
    session_id: UUID
    metric_name: str
    value_ms: float
    recorded_at: datetime

    model_config = {"from_attributes": True}


class SessionState(BaseModel):
    """Ephemeral streaming state stored in Redis."""

    session_id: UUID
    phase: SessionPhase = SessionPhase.IDLE
    sequence: int = 0
    interrupt: bool = False
    last_heartbeat: datetime | None = None
    config: dict = Field(default_factory=dict)


class TurnMetrics(BaseModel):
    stt_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_first_byte_ms: float | None = None
    e2e_ms: float | None = None
