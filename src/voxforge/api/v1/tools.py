from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import (
    get_mcp_registry,
    get_session_manager,
    get_tool_router,
    require_scope,
)
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.mcp import MCPRegistryHealth, MCPServerRecord
from voxforge.core.domain.tools import ToolDefinition
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.db.tool_repository import ToolCallRepository
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry
from voxforge.modules.mcp_tool_router.application.router import ToolRouter
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(tags=["tools"])


class ToolDefinitionResponse(BaseModel):
    name: str
    description: str
    parameters: dict
    source: str
    server_id: str | None = None
    version: str | None = None
    required_scopes: list[str] = Field(default_factory=list)


class MCPServerResponse(BaseModel):
    server_id: str
    name: str
    transport: str
    status: str
    version: str | None
    tool_count: int
    permissions: list[str]
    capabilities: list[str]
    discovery_source: str
    last_discovered_at: str | None
    last_error: str | None


class MCPServerListResponse(BaseModel):
    servers: list[MCPServerResponse]


class MCPHealthResponse(BaseModel):
    status: str
    server_count: int
    healthy_count: int
    degraded_count: int
    offline_count: int
    tool_count: int
    discovery_ms: float | None
    servers: list[MCPServerResponse]


class ToolListResponse(BaseModel):
    tools: list[ToolDefinitionResponse]


class ToolCallResponse(BaseModel):
    id: UUID
    tool_name: str
    arguments: dict
    result: str | None
    status: str
    latency_ms: float | None
    error: str | None
    created_at: str


class ToolCallListResponse(BaseModel):
    tool_calls: list[ToolCallResponse]
    offset: int
    limit: int


@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    principal: Principal = Depends(require_scope("sessions:read")),
    tool_router: ToolRouter | None = Depends(get_tool_router),
) -> ToolListResponse:
    if tool_router is None:
        return ToolListResponse(tools=[])

    tools = tool_router.list_tools()
    return ToolListResponse(
        tools=[_tool_to_response(t) for t in tools],
    )


@router.get("/tools/mcp/health", response_model=MCPHealthResponse)
async def mcp_health(
    principal: Principal = Depends(require_scope("sessions:read")),
    mcp_registry: MCPRuntimeRegistry | None = Depends(get_mcp_registry),
) -> MCPHealthResponse:
    if mcp_registry is None:
        return MCPHealthResponse(
            status="idle",
            server_count=0,
            healthy_count=0,
            degraded_count=0,
            offline_count=0,
            tool_count=0,
            discovery_ms=None,
            servers=[],
        )
    return _health_to_response(mcp_registry.get_health())


@router.get("/tools/mcp/servers", response_model=MCPServerListResponse)
async def list_mcp_servers(
    principal: Principal = Depends(require_scope("sessions:read")),
    mcp_registry: MCPRuntimeRegistry | None = Depends(get_mcp_registry),
) -> MCPServerListResponse:
    if mcp_registry is None:
        return MCPServerListResponse(servers=[])
    return MCPServerListResponse(
        servers=[_server_to_response(server) for server in mcp_registry.list_servers()]
    )


@router.get("/sessions/{session_id}/tool-calls", response_model=ToolCallListResponse)
async def list_session_tool_calls(
    session_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_scope("sessions:read")),
    session_manager: SessionManager = Depends(get_session_manager),
    db: AsyncSession = Depends(get_db_session),
) -> ToolCallListResponse:
    try:
        await session_manager.get_session(session_id, org_id=principal.org_id)
        repo = ToolCallRepository(db)
        calls = await repo.list_for_session(
            session_id, org_id=principal.org_id, offset=offset, limit=limit
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return ToolCallListResponse(
        tool_calls=[
            ToolCallResponse(
                id=c.id,
                tool_name=c.tool_name,
                arguments=c.arguments,
                result=c.result,
                status=c.status.value,
                latency_ms=c.latency_ms,
                error=c.error,
                created_at=c.created_at.isoformat(),
            )
            for c in calls
        ],
        offset=offset,
        limit=limit,
    )


def _tool_to_response(tool: ToolDefinition) -> ToolDefinitionResponse:
    return ToolDefinitionResponse(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
        source=tool.source,
        server_id=tool.server_id,
        version=tool.version,
        required_scopes=tool.required_scopes,
    )


def _server_to_response(server: MCPServerRecord) -> MCPServerResponse:
    return MCPServerResponse(
        server_id=server.server_id,
        name=server.name,
        transport=server.transport,
        status=server.status.value,
        version=server.version,
        tool_count=server.tool_count,
        permissions=server.permissions,
        capabilities=server.capabilities,
        discovery_source=server.discovery_source,
        last_discovered_at=(
            server.last_discovered_at.isoformat() if server.last_discovered_at else None
        ),
        last_error=server.last_error,
    )


def _health_to_response(health: MCPRegistryHealth) -> MCPHealthResponse:
    return MCPHealthResponse(
        status=health.status,
        server_count=health.server_count,
        healthy_count=health.healthy_count,
        degraded_count=health.degraded_count,
        offline_count=health.offline_count,
        tool_count=health.tool_count,
        discovery_ms=health.discovery_ms,
        servers=[_server_to_response(server) for server in health.servers],
    )
