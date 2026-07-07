import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from voxforge.api.ws.auth import resolve_ws_principal
from voxforge.config import get_settings
from voxforge.core.domain.entities import TransportType
from voxforge.core.domain.events import AudioChunk, TranscriptEvent
from voxforge.core.events.bus import get_event_bus
from voxforge.core.exceptions import ForbiddenError, SessionNotFoundError, UnauthorizedError
from voxforge.infrastructure.db.session import get_engine
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import active_sessions, ws_connections
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider
from voxforge.infrastructure.providers.tts.cartesia import CartesiaTTSProvider
from voxforge.infrastructure.redis.client import get_redis
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.auth.application.service import AuthService
from voxforge.modules.conversation.application.engine import ConversationEngine
from voxforge.modules.session_manager.application.service import SessionManager
from voxforge.modules.voice_gateway.application.pipeline import (
    PipelineCallbacks,
    VoicePipelineService,
)

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/api/v1/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_connections.inc()
    settings = get_settings()

    session_id: UUID | None = None
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    listening_task: asyncio.Task | None = None
    heartbeat_task: asyncio.Task | None = None

    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db_session:
            state_store = RedisSessionStateStore(
                get_redis(), ttl_seconds=settings.session_state_ttl_seconds
            )
            event_bus = get_event_bus()
            auth_service = AuthService(db_session, settings)
            session_manager = SessionManager(db_session, state_store, event_bus, settings)
            stt = DeepgramSTTProvider(settings.deepgram_api_key)
            llm = OpenAILLMProvider(settings.openai_api_key)
            tts = CartesiaTTSProvider(settings.cartesia_api_key)
            conversation = ConversationEngine(llm, settings)
            pipeline = VoicePipelineService(session_manager, stt, conversation, tts, settings)

            while True:
                message = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                if "text" in message:
                    result = await _handle_control_message(
                        message["text"],
                        websocket=websocket,
                        session_manager=session_manager,
                        auth_service=auth_service,
                        conversation=conversation,
                        pipeline=pipeline,
                        audio_queue=audio_queue,
                        session_id=session_id,
                        listening_task=listening_task,
                        heartbeat_task=heartbeat_task,
                        settings=settings,
                    )
                    session_id = result.get("session_id", session_id)
                    if result.get("listening_task"):
                        listening_task = result["listening_task"]
                    if result.get("heartbeat_task"):
                        heartbeat_task = result["heartbeat_task"]
                    if result.get("session_id") is None and session_id is not None:
                        session_id = None

                elif "bytes" in message and session_id is not None:
                    await audio_queue.put(message["bytes"])

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=str(session_id))
    except Exception as exc:
        logger.error("ws_error", session_id=str(session_id), error=str(exc))
        try:
            await websocket.send_json(
                {"type": "error", "code": "internal_error", "message": str(exc)}
            )
        except Exception:
            pass
    finally:
        ws_connections.dec()
        if listening_task and not listening_task.done():
            listening_task.cancel()
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
        await audio_queue.put(None)
        if session_id is not None:
            active_sessions.dec()
            try:
                async with session_factory() as db_session:
                    state_store = RedisSessionStateStore(
                        get_redis(), ttl_seconds=settings.session_state_ttl_seconds
                    )
                    sm = SessionManager(db_session, state_store, get_event_bus(), settings)
                    await sm.end_session(session_id, reason="disconnect")
                    await db_session.commit()
            except Exception:
                pass


async def _handle_control_message(
    raw: str,
    *,
    websocket: WebSocket,
    session_manager: SessionManager,
    auth_service: AuthService,
    conversation: ConversationEngine,
    pipeline: VoicePipelineService,
    audio_queue: asyncio.Queue,
    session_id: UUID | None,
    listening_task: asyncio.Task | None,
    heartbeat_task: asyncio.Task | None,
    settings,
) -> dict:
    result: dict = {}

    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json(
            {"type": "error", "code": "invalid_json", "message": "Invalid JSON"}
        )
        return result

    msg_type = msg.get("type")

    if msg_type == "start":
        config = msg.get("config", {})
        resume_id = msg.get("session_id")

        try:
            principal = await resolve_ws_principal(websocket, auth_service, settings, msg)
        except (UnauthorizedError, ForbiddenError) as exc:
            await websocket.send_json({"type": "error", "code": exc.code, "message": exc.message})
            return result

        if resume_id:
            try:
                session = await session_manager.get_session(
                    UUID(resume_id), org_id=principal.org_id
                )
                session = await session_manager.resume_session(
                    UUID(resume_id), msg.get("last_sequence", 0)
                )
            except SessionNotFoundError:
                await websocket.send_json(
                    {"type": "error", "code": "session_not_found", "message": "Session not found"}
                )
                return result
        else:
            session = await session_manager.create_session(
                transport_type=TransportType.WEBSOCKET,
                config=config,
                org_id=principal.org_id,
                created_by_user_id=principal.user_id,
            )

        session = await session_manager.activate_session(session.id)
        await session_manager.commit()

        conversation.init_session(session.id)
        messages = await session_manager.get_messages(session.id)
        if messages:
            conversation.load_history(session.id, messages)

        result["session_id"] = session.id
        active_sessions.inc()

        callbacks = _build_callbacks(websocket)
        sid = session.id

        async def listen():
            await pipeline.run_listening(
                sid,
                audio_queue,
                callbacks,
                language=config.get("language"),
            )

        result["listening_task"] = asyncio.create_task(listen())

        async def heartbeat_loop():
            while True:
                await asyncio.sleep(settings.session_heartbeat_interval_seconds)
                await session_manager.record_heartbeat(sid)

        result["heartbeat_task"] = asyncio.create_task(heartbeat_loop())

        await websocket.send_json({"type": "started", "session_id": str(session.id)})

    elif msg_type == "interrupt":
        if session_id:
            await pipeline.interrupt(session_id)
            await websocket.send_json({"type": "interrupted"})

    elif msg_type == "end":
        if session_id:
            await audio_queue.put(None)
            if listening_task and not listening_task.done():
                listening_task.cancel()
            if heartbeat_task and not heartbeat_task.done():
                heartbeat_task.cancel()
            await session_manager.end_session(session_id)
            await session_manager.commit()
            conversation.clear_session(session_id)
            active_sessions.dec()
            result["session_id"] = None
            await websocket.send_json({"type": "ended", "session_id": str(session_id)})

    elif msg_type == "ping":
        if session_id:
            await session_manager.record_heartbeat(session_id)
        await websocket.send_json({"type": "pong"})

    return result


def _build_callbacks(websocket: WebSocket) -> PipelineCallbacks:
    async def on_transcript(event: TranscriptEvent) -> None:
        await websocket.send_json({
            "type": "transcript",
            "partial": event.is_partial,
            "text": event.text,
            "confidence": event.confidence,
            "language": event.language,
        })

    async def on_token(text: str) -> None:
        await websocket.send_json({"type": "response", "token": text})

    async def on_audio(chunk: AudioChunk) -> None:
        await websocket.send_bytes(chunk.data)

    async def on_metrics(metrics) -> None:
        await websocket.send_json({
            "type": "metric",
            "stt_ms": metrics.stt_ms,
            "llm_first_token_ms": metrics.llm_first_token_ms,
            "tts_first_byte_ms": metrics.tts_first_byte_ms,
            "e2e_ms": metrics.e2e_ms,
        })

    async def on_error(code: str, message: str) -> None:
        await websocket.send_json({"type": "error", "code": code, "message": message})

    return PipelineCallbacks(
        on_transcript=on_transcript,
        on_token=on_token,
        on_audio=on_audio,
        on_metrics=on_metrics,
        on_error=on_error,
    )
