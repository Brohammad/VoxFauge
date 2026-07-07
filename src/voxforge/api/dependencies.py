from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.config import Settings, get_settings
from voxforge.core.events.bus import EventBus, get_event_bus
from voxforge.infrastructure.db.session import get_db_session
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider
from voxforge.infrastructure.providers.tts.cartesia import CartesiaTTSProvider
from voxforge.infrastructure.redis.client import get_redis
from voxforge.infrastructure.redis.session_state import RedisSessionStateStore
from voxforge.modules.conversation.application.engine import ConversationEngine
from voxforge.modules.session_manager.application.service import SessionManager
from voxforge.modules.voice_gateway.application.pipeline import VoicePipelineService


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
