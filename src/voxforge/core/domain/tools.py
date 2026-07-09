from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ToolCallStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict = Field(default_factory=dict)
    source: str = "builtin"  # builtin | mcp
    server_id: str | None = None
    version: str | None = None
    required_scopes: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    tool_name: str
    output: str
    status: ToolCallStatus = ToolCallStatus.SUCCESS
    latency_ms: float | None = None
    error: str | None = None


class ToolCallRecord(BaseModel):
    id: UUID
    org_id: UUID | None
    session_id: UUID | None
    tool_name: str
    arguments: dict
    result: str | None
    status: ToolCallStatus
    latency_ms: float | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
