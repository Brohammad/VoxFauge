from typing import Annotated

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings, get_settings
from voxforge.core.domain.auth import Principal
from voxforge.core.events.bus import EventBus, get_event_bus
from voxforge.core.exceptions import ForbiddenError, UnauthorizedError
from voxforge.infrastructure.db.dashboard_repository import DashboardRepository
from voxforge.infrastructure.db.evaluation_repository import EvaluationRepository
from voxforge.infrastructure.db.memory_repository import MemoryRepository
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.db.tool_repository import ToolCallRepository
from voxforge.infrastructure.livekit.token_service import LiveKitTokenService
from voxforge.infrastructure.providers.embeddings.openai import OpenAIEmbeddingProvider
from voxforge.infrastructure.providers.factory import (
    create_llm_provider,
    create_stt_provider,
    create_tts_provider,
)
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.redis.client import get_redis
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.infrastructure.tools.mcp_adapter import MCPToolAdapter
from voxforge.modules.agent_orchestrator.application.factory import create_response_generator
from voxforge.modules.auth.application.service import AuthService
from voxforge.modules.dashboard.application.service import DashboardService
from voxforge.modules.evaluation.application.service import EvaluationEngine
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry
from voxforge.modules.mcp_tool_router.application.router import ToolRouter
from voxforge.modules.memory.application.service import MemoryService
from voxforge.modules.onboarding.application.service import OnboardingService
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


def get_stt_provider(settings: Settings = Depends(get_settings)):
    return create_stt_provider(settings)


def get_llm_provider(settings: Settings = Depends(get_settings)):
    return create_llm_provider(settings)


def get_tts_provider(settings: Settings = Depends(get_settings)):
    return create_tts_provider(settings)


def get_livekit_service(settings: Settings = Depends(get_settings)) -> LiveKitTokenService:
    return LiveKitTokenService(settings)


def get_memory_service(
    db: AsyncSession = Depends(get_db_session),
    llm: OpenAILLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> MemoryService | None:
    if not settings.memory_enabled:
        return None
    store = MemoryRepository(db)
    embedder = OpenAIEmbeddingProvider(
        settings.openai_api_key,
        model=settings.memory_embedding_model,
    )
    return MemoryService(store, embedder, settings, llm)


def get_tool_router(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ToolRouter | None:
    if not settings.tools_enabled:
        return None
    mcp = MCPToolAdapter(settings.mcp_servers_config) if settings.mcp_servers_config else None
    registry = ToolRegistry(mcp)
    repo = ToolCallRepository(db)
    return ToolRouter(registry, settings, repo)


def get_evaluation_engine(
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    llm=Depends(get_llm_provider),
) -> EvaluationEngine | None:
    if not settings.evaluation_enabled:
        return None
    return EvaluationEngine(EvaluationRepository(db), settings, llm)


def get_dashboard_service(
    db: AsyncSession = Depends(get_db_session),
) -> DashboardService:
    return DashboardService(DashboardRepository(db))


def get_onboarding_service(
    db: AsyncSession = Depends(get_db_session),
) -> OnboardingService:
    return OnboardingService(db)


def get_response_generator(
    llm: OpenAILLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
    memory_service: MemoryService | None = Depends(get_memory_service),
    tool_router: ToolRouter | None = Depends(get_tool_router),
):
    return create_response_generator(settings, llm, memory_service, tool_router)


def get_pipeline(
    session_manager: SessionManager = Depends(get_session_manager),
    stt=Depends(get_stt_provider),
    response_generator=Depends(get_response_generator),
    tts=Depends(get_tts_provider),
    settings: Settings = Depends(get_settings),
    memory_service: MemoryService | None = Depends(get_memory_service),
    evaluation_engine: EvaluationEngine | None = Depends(get_evaluation_engine),
) -> VoicePipelineService:
    return VoicePipelineService(
        session_manager,
        stt,
        response_generator,
        tts,
        settings,
        memory_service,
        evaluation_engine,
    )
