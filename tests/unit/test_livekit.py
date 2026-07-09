"""Tests for LiveKit token service."""

from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.exceptions import ProviderError
from voxforge.infrastructure.livekit.token_service import LiveKitTokenService


def test_livekit_disabled_without_config():
    svc = LiveKitTokenService(
        Settings(
            livekit_url="",
            livekit_api_key="",
            livekit_api_secret="",
        )
    )
    assert svc.enabled is False
    with pytest.raises(ProviderError):
        svc.create_participant_token(
            session_id=uuid4(),
            participant_identity="user-1",
        )


@pytest.mark.skipif(
    True,
    reason="Requires livekit-api and configured keys",
)
def test_livekit_token_generation():
    svc = LiveKitTokenService(
        Settings(
            livekit_url="wss://example.livekit.cloud",
            livekit_api_key="key",
            livekit_api_secret="secret",
        )
    )
    result = svc.create_participant_token(
        session_id=uuid4(),
        participant_identity="user-1",
    )
    assert result["token"]
    assert result["room_name"].startswith("voxforge-")
