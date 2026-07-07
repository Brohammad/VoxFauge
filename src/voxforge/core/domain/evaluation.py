from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class MetricName(StrEnum):
    LATENCY = "latency"
    TASK_COMPLETION = "task_completion"
    TOOL_ACCURACY = "tool_accuracy"
    CONVERSATION_QUALITY = "conversation_quality"
    COST = "cost"


class EvaluationMetric(BaseModel):
    name: MetricName
    score: float  # 0.0 - 1.0
    value: float | None = None
    unit: str | None = None
    status: EvaluationStatus
    details: dict = Field(default_factory=dict)


class TurnEvaluationInput(BaseModel):
    session_id: UUID
    org_id: UUID | None = None
    user_transcript: str
    assistant_response: str
    stt_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_first_byte_ms: float | None = None
    e2e_ms: float | None = None
    tool_calls: list[dict] = Field(default_factory=list)
    interrupted: bool = False
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0


class EvaluationRun(BaseModel):
    id: UUID
    org_id: UUID | None
    session_id: UUID
    user_transcript: str
    assistant_response: str
    overall_score: float
    overall_status: EvaluationStatus
    metrics: list[EvaluationMetric]
    created_at: datetime

    model_config = {"from_attributes": True}
