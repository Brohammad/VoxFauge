from pydantic import BaseModel, Field


class AlertThresholds(BaseModel):
    task_success_min: float = 0.8
    escalation_max: float = 0.35
    quality_min: float = 0.75
    e2e_latency_max_ms: float = 2000.0
    failed_evaluation_max_rate: float = 0.2


class AlertItem(BaseModel):
    code: str
    severity: str  # warning | critical
    metric: str
    observed: float
    threshold: float
    message: str


class AlertSummary(BaseModel):
    active_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    thresholds: AlertThresholds = Field(default_factory=AlertThresholds)
    alerts: list[AlertItem] = Field(default_factory=list)
