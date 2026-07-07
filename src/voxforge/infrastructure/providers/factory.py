"""Provider factory — select STT, LLM, and TTS backends via settings."""

from voxforge.config import Settings
from voxforge.core.exceptions import ProviderError
from voxforge.core.interfaces.providers import LLMProvider, SpeechProvider, TTSProvider
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.providers.mock import MockLLMProvider, MockSTTProvider, MockTTSProvider
from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider
from voxforge.infrastructure.providers.tts.cartesia import CartesiaTTSProvider


def create_stt_provider(settings: Settings) -> SpeechProvider:
    provider = settings.stt_provider.lower()
    if provider == "deepgram":
        return DeepgramSTTProvider(settings.deepgram_api_key)
    if provider == "mock":
        return MockSTTProvider()
    raise ProviderError("factory", f"Unknown STT provider: {provider}")


def create_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return OpenAILLMProvider(settings.openai_api_key)
    if provider == "mock":
        return MockLLMProvider()
    raise ProviderError("factory", f"Unknown LLM provider: {provider}")


def create_tts_provider(settings: Settings) -> TTSProvider:
    provider = settings.tts_provider.lower()
    if provider == "cartesia":
        return CartesiaTTSProvider(settings.cartesia_api_key)
    if provider == "mock":
        return MockTTSProvider()
    raise ProviderError("factory", f"Unknown TTS provider: {provider}")
