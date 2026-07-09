"""LiveKit agent dispatch for room jobs."""

from __future__ import annotations

from voxforge.config import Settings
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import livekit_dispatch_total

logger = get_logger(__name__)


class LiveKitDispatchService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return bool(
            self._settings.livekit_dispatch_enabled
            and self._settings.livekit_url
            and self._settings.livekit_api_key
            and self._settings.livekit_api_secret
            and self._settings.livekit_agent_name
        )

    async def dispatch_agent(self, room_name: str) -> bool:
        if not self.enabled:
            livekit_dispatch_total.labels(status="skipped").inc()
            return False
        try:
            from livekit import api
        except ImportError:
            logger.warning("livekit_dispatch_import_failed")
            livekit_dispatch_total.labels(status="error").inc()
            return False

        try:
            lkapi = api.LiveKitAPI(
                self._settings.livekit_url,
                self._settings.livekit_api_key,
                self._settings.livekit_api_secret,
            )
            await lkapi.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    room=room_name,
                    agent_name=self._settings.livekit_agent_name,
                )
            )
            await lkapi.aclose()
            livekit_dispatch_total.labels(status="success").inc()
            logger.info("livekit_agent_dispatched", room=room_name)
            return True
        except Exception as exc:
            livekit_dispatch_total.labels(status="error").inc()
            logger.warning(
                "livekit_agent_dispatch_failed",
                room=room_name,
                error=str(exc),
            )
            return False
