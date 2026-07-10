"""Shared fixtures for Playwright browser tests."""

from __future__ import annotations

import os

import pytest

# Playwright base URL — set by scripts/run_browser_tests.sh or CI.
DEFAULT_BASE = os.environ.get("VOXFORGE_BROWSER_BASE_URL", "http://127.0.0.1:8765")


@pytest.fixture(scope="session")
def browser_context_args():
    return {"base_url": DEFAULT_BASE}


@pytest.fixture(scope="session")
def base_url() -> str:
    return DEFAULT_BASE
