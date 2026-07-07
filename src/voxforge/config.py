from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://voxforge:voxforge@localhost:5432/voxforge"
    redis_url: str = "redis://localhost:6379/0"

    deepgram_api_key: str = ""
    openai_api_key: str = ""
    cartesia_api_key: str = ""

    default_llm_model: str = "gpt-4o-mini"
    default_tts_voice_id: str = "79a125e8-cd45-4c13-8a67-188112f4dd22"

    otel_exporter_otlp_endpoint: str = ""

    session_heartbeat_interval_seconds: int = 15
    session_stale_timeout_seconds: int = 45
    session_state_ttl_seconds: int = 3600

    system_prompt: str = (
        "You are a helpful voice assistant. Keep responses concise and conversational "
        "since they will be spoken aloud."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
