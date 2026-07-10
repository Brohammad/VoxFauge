"""Shared fixtures for feature-flow tests."""

import pytest

from voxforge.config import get_settings


@pytest.fixture(autouse=True)
def feature_stack(monkeypatch, tmp_path):
    """Enable full platform features with mock providers for feature tests."""
    monkeypatch.setenv("STT_PROVIDER", "mock")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("HANDOFF_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_ENABLED", "true")
    monkeypatch.setenv("KNOWLEDGE_WORKER_ENABLED", "false")
    monkeypatch.setenv("KNOWLEDGE_BLOB_PATH", str(tmp_path / "kb"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("TOOLS_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
