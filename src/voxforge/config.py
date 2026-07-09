from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    public_base_url: str = ""
    trusted_hosts: str = ""
    cors_origins: str = ""

    demo_enabled: bool = False
    demo_org_id: str = "a0000000-0000-4000-8000-000000000001"
    demo_user_id: str = "a0000000-0000-4000-8000-000000000002"
    demo_email: str = "demo@voxforge.io"
    demo_password_hint: str = "VoxForgeDemo!"

    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 60
    rate_limit_paths: str = "/api/v1/auth,/api/v1/demo"

    database_url: str = "postgresql+asyncpg://voxforge:voxforge@localhost:5432/voxforge"
    redis_url: str = "redis://localhost:6379/0"

    deepgram_api_key: str = ""
    openai_api_key: str = ""
    cartesia_api_key: str = ""

    stt_provider: str = "deepgram"  # deepgram | mock
    llm_provider: str = "openai"  # openai | mock
    tts_provider: str = "cartesia"  # cartesia | mock

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_agent_name: str = "voxforge-voice"
    livekit_dispatch_enabled: bool = True
    livekit_reconnect_grace_seconds: int = 30

    default_llm_model: str = "gpt-4.1-mini"
    default_tts_voice_id: str = "79a125e8-cd45-4c13-8a67-188112f4dd22"

    otel_exporter_otlp_endpoint: str = ""

    session_heartbeat_interval_seconds: int = 15
    session_stale_timeout_seconds: int = 45
    session_state_ttl_seconds: int = 3600

    system_prompt: str = (
        "You are a helpful voice assistant. Keep responses concise and conversational "
        "since they will be spoken aloud."
    )

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    api_key_prefix: str = "vxf_"
    api_key_hash_pepper: str = "change-me-in-production"

    auth_required: bool = True
    saml_require_signed_assertions: bool = True
    saml_clock_skew_seconds: int = 120

    orchestrator_mode: str = "single"  # single | multi_agent
    max_agent_iterations: int = 2
    planner_model: str = "gpt-4.1-mini"
    executor_model: str = "gpt-4.1-mini"
    critic_model: str = "gpt-4.1-mini"
    safety_model: str = "gpt-4.1-mini"
    coordinator_model: str = "gpt-4.1-mini"

    memory_enabled: bool = True
    memory_embedding_model: str = "text-embedding-3-small"
    memory_embedding_dimensions: int = 1536
    memory_max_recent_messages: int = 10
    memory_summarize_after_messages: int = 20
    memory_retrieval_top_k: int = 5
    memory_similarity_threshold: float = 0.65
    memory_summary_model: str = "gpt-4.1-mini"

    tools_enabled: bool = True
    tool_timeout_seconds: int = 30
    max_tool_iterations: int = 5
    mcp_servers_config: str = ""  # JSON array of MCP server configs
    mcp_discovery_enabled: bool = True
    mcp_discovery_timeout_ms: float = 5000.0
    mcp_startup_discover: bool = True

    evaluation_enabled: bool = True
    evaluation_e2e_target_ms: float = 2000.0
    evaluation_llm_input_cost_per_1k: float = 0.00015
    evaluation_llm_output_cost_per_1k: float = 0.0006
    evaluation_turn_cost_budget_usd: float = 0.01
    evaluation_hallucination_enabled: bool = True
    evaluation_judge_model: str = "gpt-4.1-mini"
    evaluation_min_hallucination_score: float = 0.7

    @property
    def rate_limit_path_prefixes(self) -> tuple[str, ...]:
        return tuple(p.strip() for p in self.rate_limit_paths.split(",") if p.strip())

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
