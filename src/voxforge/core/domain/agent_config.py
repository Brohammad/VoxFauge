from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyPreset(BaseModel):
    slug: str
    name: str
    description: str
    source: str
    prompt_config: dict = Field(default_factory=dict)
    orchestrator_config: dict = Field(default_factory=dict)
    eval_thresholds: dict = Field(default_factory=dict)
    tool_config: dict = Field(default_factory=dict)


class AgentConfigVersion(BaseModel):
    id: UUID
    org_id: UUID
    version: int
    label: str
    prompt_config: dict = Field(default_factory=dict)
    orchestrator_config: dict = Field(default_factory=dict)
    eval_thresholds: dict = Field(default_factory=dict)
    is_active: bool = False
    created_by_user_id: UUID | None = None
    change_note: str | None = None
    created_at: datetime
