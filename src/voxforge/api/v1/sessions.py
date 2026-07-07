from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_session_manager
from voxforge.core.domain.entities import SessionStatus, TransportType, VoiceSession
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    transport_type: TransportType = TransportType.WEBSOCKET
    config: dict = Field(default_factory=dict)


class CreateSessionResponse(BaseModel):
    session_id: UUID
    ws_url: str
    status: SessionStatus


class SessionResponse(BaseModel):
    id: UUID
    status: SessionStatus
    transport_type: TransportType
    metadata: dict
    started_at: str
    ended_at: str | None = None
    total_latency_ms: float | None = None

    @classmethod
    def from_entity(cls, session: VoiceSession) -> "SessionResponse":
        return cls(
            id=session.id,
            status=session.status,
            transport_type=session.transport_type,
            metadata=session.metadata,
            started_at=session.started_at.isoformat(),
            ended_at=session.ended_at.isoformat() if session.ended_at else None,
            total_latency_ms=session.total_latency_ms,
        )


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    content_type: str
    created_at: str


class MessagesListResponse(BaseModel):
    messages: list[MessageResponse]
    offset: int
    limit: int


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    session_manager: SessionManager = Depends(get_session_manager),
    db: AsyncSession = Depends(get_db_session),
) -> CreateSessionResponse:
    session = await session_manager.create_session(
        transport_type=body.transport_type,
        config=body.config,
    )
    await session_manager.commit()
    return CreateSessionResponse(
        session_id=session.id,
        ws_url="/api/v1/ws/voice",
        status=session.status,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    session_manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    try:
        session = await session_manager.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return SessionResponse.from_entity(session)


@router.get("/{session_id}/messages", response_model=MessagesListResponse)
async def get_messages(
    session_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session_manager: SessionManager = Depends(get_session_manager),
) -> MessagesListResponse:
    try:
        messages = await session_manager.get_messages(session_id, offset=offset, limit=limit)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return MessagesListResponse(
        messages=[
            MessageResponse(
                id=m.id,
                session_id=m.session_id,
                role=m.role.value,
                content=m.content,
                content_type=m.content_type,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
        offset=offset,
        limit=limit,
    )


@router.delete("/{session_id}", response_model=SessionResponse)
async def end_session(
    session_id: UUID,
    session_manager: SessionManager = Depends(get_session_manager),
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    try:
        session = await session_manager.end_session(session_id)
        await session_manager.commit()
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return SessionResponse.from_entity(session)
