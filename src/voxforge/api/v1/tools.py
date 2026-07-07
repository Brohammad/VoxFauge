from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_session_manager, get_tool_router, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.tools import ToolDefinition
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.db.tool_repository import ToolCallRepository
from voxforge.modules.mcp_tool_router.application.router import ToolRouter
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(tags=["tools"])


class ToolDefinitionResponse(BaseModel):
    name: str
    description: str
    parameters: dict
    source: str


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
    )
