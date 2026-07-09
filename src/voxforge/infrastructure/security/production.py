"""Production security and configuration validation."""

from __future__ import annotations

from uuid import UUID

from voxforge.config import Settings

_INSECURE_MARKERS = ("change-me", "changeme", "replace-me", "your-secret")


def _is_insecure_secret(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _INSECURE_MARKERS)


def collect_production_errors(settings: Settings) -> list[str]:
    if settings.app_env != "production":
        return []

    errors: list[str] = []

    if _is_insecure_secret(settings.jwt_secret_key):
        errors.append("JWT_SECRET_KEY must be set to a strong unique value")
    if _is_insecure_secret(settings.api_key_hash_pepper):
        errors.append("API_KEY_HASH_PEPPER must be set to a strong unique value")
    if len(settings.jwt_secret_key) < 32:
        errors.append("JWT_SECRET_KEY should be at least 32 characters")

    if settings.demo_enabled:
        if not settings.demo_org_id or not settings.demo_user_id:
            errors.append("DEMO_ORG_ID and DEMO_USER_ID are required when DEMO_ENABLED=true")
        else:
            try:
                UUID(settings.demo_org_id)
                UUID(settings.demo_user_id)
            except ValueError:
                errors.append("DEMO_ORG_ID and DEMO_USER_ID must be valid UUIDs")

    if settings.stt_provider.lower() == "deepgram" and not settings.deepgram_api_key:
        errors.append("DEEPGRAM_API_KEY is required when STT_PROVIDER=deepgram")
    if settings.llm_provider.lower() == "openai" and not settings.openai_api_key:
        errors.append("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
    if settings.tts_provider.lower() == "cartesia" and not settings.cartesia_api_key:
        errors.append("CARTESIA_API_KEY is required when TTS_PROVIDER=cartesia")

    if settings.trusted_hosts.strip() in ("", "*"):
        errors.append("TRUSTED_HOSTS must list your public domain(s) in production")

    return errors


def validate_production_settings(settings: Settings) -> None:
    errors = collect_production_errors(settings)
    if errors:
        raise RuntimeError("Production configuration invalid: " + "; ".join(errors))
