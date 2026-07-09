"""LiveKit WebRTC token generation for voice sessions."""

from uuid import UUID

from voxforge.config import Settings
from voxforge.core.exceptions import ProviderError
from voxforge.infrastructure.livekit.room_utils import room_name_for_session


class LiveKitTokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.livekit_url
            and self._settings.livekit_api_key
            and self._settings.livekit_api_secret
        )

    def create_participant_token(
        self,
        *,
        session_id: UUID,
        participant_identity: str,
        participant_name: str | None = None,
    ) -> dict[str, str]:
        if not self.enabled:
            raise ProviderError("livekit", "LiveKit is not configured")

        try:
            from livekit.api import AccessToken, VideoGrants
        except ImportError as exc:
            raise ProviderError(
                "livekit",
                "livekit-api not installed; pip install -e '.[livekit]'",
            ) from exc

        room_name = room_name_for_session(session_id)
        grants = VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        )
        token = (
            AccessToken(self._settings.livekit_api_key, self._settings.livekit_api_secret)
            .with_identity(participant_identity)
            .with_name(participant_name or participant_identity)
            .with_grants(grants)
            .to_jwt()
        )
        return {
            "token": token,
            "room_name": room_name,
            "livekit_url": self._settings.livekit_url,
        }
