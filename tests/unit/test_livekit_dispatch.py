"""Unit tests for LiveKit agent dispatch."""

import pytest

from voxforge.config import Settings
from voxforge.infrastructure.livekit.dispatch_service import LiveKitDispatchService


@pytest.mark.asyncio
async def test_dispatch_skipped_when_disabled():
    svc = LiveKitDispatchService(
        Settings(
            livekit_dispatch_enabled=False,
            livekit_url="wss://example.livekit.cloud",
            livekit_api_key="k",
            livekit_api_secret="s",
            livekit_agent_name="voxforge-voice",
        )
    )
    assert await svc.dispatch_agent("voxforge-test") is False


@pytest.mark.asyncio
async def test_dispatch_skipped_without_agent_name():
    svc = LiveKitDispatchService(
        Settings(
            livekit_dispatch_enabled=True,
            livekit_url="wss://example.livekit.cloud",
            livekit_api_key="k",
            livekit_api_secret="s",
            livekit_agent_name="",
        )
    )
    assert svc.enabled is False
