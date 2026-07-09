from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MCPServerStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MCPServerRecord(BaseModel):
    server_id: str
    name: str
    transport: str
    status: MCPServerStatus
    version: str | None = None
    tool_count: int = 0
    permissions: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    discovery_source: str = "runtime"  # runtime | static
    last_discovered_at: datetime | None = None
    last_error: str | None = None


class MCPRegistryHealth(BaseModel):
    status: str
    server_count: int
    healthy_count: int
    degraded_count: int
    offline_count: int
    tool_count: int
    discovery_ms: float | None = None
    servers: list[MCPServerRecord] = Field(default_factory=list)
