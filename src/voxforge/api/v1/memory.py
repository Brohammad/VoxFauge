from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from voxforge.api.dependencies import (
    get_memory_service,
    get_session_manager,
    rate_limit_category,
    require_scope,
)
from voxforge.core.domain.auth import Principal
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.modules.memory.application.service import MemoryService
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(prefix="/sessions", tags=["memory"])


class MemoryEntryResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    entry_type: str
    similarity: float | None = None
    created_at: str


class MemoryListResponse(BaseModel):
    entries: list[MemoryEntryResponse]
    offset: int
    limit: int


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


@router.get("/{session_id}/memory", response_model=MemoryListResponse)
async def list_memory(
    session_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_scope("sessions:read")),
    session_manager: SessionManager = Depends(get_session_manager),
    memory_service: MemoryService | None = Depends(get_memory_service),
) -> MemoryListResponse:
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory module is disabled")

    try:
        await session_manager.get_session(session_id, org_id=principal.org_id)
        entries = await memory_service.list_entries(
            org_id=principal.org_id,
            session_id=session_id,
            offset=offset,
            limit=limit,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return MemoryListResponse(
        entries=[
            MemoryEntryResponse(
                id=e.id,
                session_id=e.session_id,
                role=e.role,
                content=e.content,
                entry_type=e.entry_type.value,
                similarity=e.similarity,
                created_at=e.created_at.isoformat(),
            )
            for e in entries
        ],
        offset=offset,
        limit=limit,
    )


@router.post("/{session_id}/memory/search", response_model=MemoryListResponse)
async def search_memory(
    session_id: UUID,
    body: MemorySearchRequest,
    _: None = Depends(rate_limit_category("memory_search")),
    principal: Principal = Depends(require_scope("sessions:read")),
    session_manager: SessionManager = Depends(get_session_manager),
    memory_service: MemoryService | None = Depends(get_memory_service),
) -> MemoryListResponse:
    if memory_service is None:
        raise HTTPException(status_code=503, detail="Memory module is disabled")

    try:
        await session_manager.get_session(session_id, org_id=principal.org_id)
        entries = await memory_service.search(
            org_id=principal.org_id,
            session_id=session_id,
            query=body.query,
            limit=body.limit,
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return MemoryListResponse(
        entries=[
            MemoryEntryResponse(
                id=e.id,
                session_id=e.session_id,
                role=e.role,
                content=e.content,
                entry_type=e.entry_type.value,
                similarity=e.similarity,
                created_at=e.created_at.isoformat(),
            )
            for e in entries
        ],
        offset=0,
        limit=body.limit,
    )
