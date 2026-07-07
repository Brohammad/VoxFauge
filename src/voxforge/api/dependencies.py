from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings, get_settings
from voxforge.core.domain.auth import Principal
from voxforge.core.events.bus import EventBus, get_event_bus
from voxforge.core.exceptions import ForbiddenError, UnauthorizedError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider
from voxforge.infrastructure.providers.tts.cartesia import CartesiaTTSProvider
from voxforge.infrastructure.redis.client import get_redis
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.auth.application.service import AuthService
from voxforge.modules.conversation.application.engine import ConversationEngine
from voxforge.modules.session_manager.application.service import SessionManager
from voxforge.modules.voice_gateway.application.pipeline import VoicePipelineService

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(db, settings)


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    api_key: Annotated[str | None, Security(api_key_header)],
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not settings.auth_required:
        from uuid import UUID

        from voxforge.core.domain.auth import OrgRole, PrincipalType

        return Principal(
            type=PrincipalType.USER,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            org_id=UUID("00000000-0000-0000-0000-000000000010"),
            role=OrgRole.OWNER,
        )

    if credentials and credentials.credentials:
        try:
            return await auth_service.resolve_principal_from_bearer(credentials.credentials)
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc

    if api_key:
        try:
            return await auth_service.resolve_principal_from_api_key(api_key)
        except UnauthorizedError as exc:
            raise HTTPException(status_code=401, detail=exc.message) from exc

    raise HTTPException(status_code=401, detail="Authentication required")


def require_scope(scope: str):
    async def _checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        try:
            AuthService.require_scope(principal, scope)
        except ForbiddenError as exc:
            raise HTTPException(status_code=403, detail=exc.message) from exc
        return principal

    return _checker


def get_state_store(settings: Settings = Depends(get_settings)) -> RedisSessionStateStore:
    return RedisSessionStateStore(get_redis(), ttl_seconds=settings.session_state_ttl_seconds)


def get_session_manager(
    db: AsyncSession = Depends(get_db_session),
    state_store: RedisSessionStateStore = Depends(get_state_store),
    event_bus: EventBus = Depends(get_event_bus),
    settings: Settings = Depends(get_settings),
) -> SessionManager:
    return SessionManager(db, state_store, event_bus, settings)


def get_stt_provider(settings: Settings = Depends(get_settings)) -> DeepgramSTTProvider:
    return DeepgramSTTProvider(settings.deepgram_api_key)


def get_llm_provider(settings: Settings = Depends(get_settings)) -> OpenAILLMProvider:
    return OpenAILLMProvider(settings.openai_api_key)


def get_tts_provider(settings: Settings = Depends(get_settings)) -> CartesiaTTSProvider:
    return CartesiaTTSProvider(settings.cartesia_api_key)


def get_conversation_engine(
    llm: OpenAILLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> ConversationEngine:
    return ConversationEngine(llm, settings)


def get_pipeline(
    session_manager: SessionManager = Depends(get_session_manager),
    stt: DeepgramSTTProvider = Depends(get_stt_provider),
    conversation: ConversationEngine = Depends(get_conversation_engine),
    tts: CartesiaTTSProvider = Depends(get_tts_provider),
    settings: Settings = Depends(get_settings),
) -> VoicePipelineService:
    return VoicePipelineService(session_manager, stt, conversation, tts, settings)
