from uuid import UUID

from voxforge.core.domain.replay import SessionReplay
from voxforge.infrastructure.db.replay_repository import ReplayRepository
from voxforge.infrastructure.observability.telemetry import get_tracer

_tracer = get_tracer(__name__)


class ReplayService:
    def __init__(self, repository: ReplayRepository) -> None:
        self._repository = repository

    async def get_session_replay(
        self, session_id: UUID, *, org_id: UUID | None = None
    ) -> SessionReplay:
        with _tracer.start_as_current_span("replay.get_session") as span:
            span.set_attribute("voxforge.session_id", str(session_id))
            if org_id is not None:
                span.set_attribute("voxforge.org_id", str(org_id))
            return await self._repository.get_session_replay(session_id, org_id=org_id)
