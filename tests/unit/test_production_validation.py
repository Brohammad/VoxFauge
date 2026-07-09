"""Tests for production configuration validation."""

from voxforge.config import Settings
from voxforge.infrastructure.security.production import collect_production_errors


def test_production_validation_passes_with_strong_secrets():
    settings = Settings(
        app_env="production",
        jwt_secret_key="a" * 32,
        api_key_hash_pepper="b" * 32,
        trusted_hosts="demo.example.com",
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
        demo_enabled=True,
        demo_org_id="a0000000-0000-4000-8000-000000000001",
        demo_user_id="a0000000-0000-4000-8000-000000000002",
    )
    assert collect_production_errors(settings) == []


def test_production_validation_rejects_weak_secrets():
    settings = Settings(
        app_env="production",
        jwt_secret_key="change-me-in-production",
        api_key_hash_pepper="change-me-in-production",
        trusted_hosts="demo.example.com",
    )
    errors = collect_production_errors(settings)
    assert any("JWT_SECRET_KEY" in e for e in errors)
    assert any("API_KEY_HASH_PEPPER" in e for e in errors)


def test_production_validation_requires_trusted_hosts():
    settings = Settings(
        app_env="production",
        jwt_secret_key="a" * 32,
        api_key_hash_pepper="b" * 32,
        trusted_hosts="*",
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
    )
    errors = collect_production_errors(settings)
    assert any("TRUSTED_HOSTS" in e for e in errors)


def test_development_skips_validation():
    settings = Settings(app_env="development", jwt_secret_key="change-me")
    assert collect_production_errors(settings) == []
