"""Tests for production configuration validation."""

from voxforge.config import Settings
from voxforge.infrastructure.security.production import collect_production_errors


def _production_settings(**overrides):
    base = dict(
        app_env="production",
        auth_required=True,
        jwt_secret_key="a" * 32,
        api_key_hash_pepper="b" * 32,
        handoff_replay_signing_secret="c" * 32,
        trusted_hosts="demo.example.com",
        cors_origins="https://demo.example.com",
        public_base_url="https://demo.example.com",
        metrics_allow_anonymous=False,
        metrics_bearer_token="metrics-token-secret-value",
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
        embedding_provider="mock",
        demo_enabled=True,
        demo_org_id="a0000000-0000-4000-8000-000000000001",
        demo_user_id="a0000000-0000-4000-8000-000000000002",
    )
    base.update(overrides)
    return Settings(**base)


def test_production_validation_passes_with_strong_secrets():
    assert collect_production_errors(_production_settings()) == []


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
    errors = collect_production_errors(
        _production_settings(trusted_hosts="*", demo_enabled=False)
    )
    assert any("TRUSTED_HOSTS" in e for e in errors)


def test_production_validation_rejects_mock_providers_without_demo():
    errors = collect_production_errors(
        _production_settings(demo_enabled=False, stt_provider="deepgram")
    )
    assert any("Mock voice/embedding providers" in e for e in errors)


def test_production_validation_requires_replay_signing_secret():
    errors = collect_production_errors(_production_settings(handoff_replay_signing_secret=""))
    assert any("HANDOFF_REPLAY_SIGNING_SECRET" in e for e in errors)


def test_development_skips_validation():
    settings = Settings(app_env="development", jwt_secret_key="change-me")
    assert collect_production_errors(settings) == []
