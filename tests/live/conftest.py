import os

import pytest


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.skip(f"{name} not set — skipping live test")
    return value


@pytest.fixture
def openai_api_key() -> str:
    return _require_env("OPENAI_API_KEY")


@pytest.fixture
def deepgram_api_key() -> str:
    return _require_env("DEEPGRAM_API_KEY")


@pytest.fixture
def cartesia_api_key() -> str:
    return _require_env("CARTESIA_API_KEY")
