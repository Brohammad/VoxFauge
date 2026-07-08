from uuid import UUID

from voxforge.core.domain.replay import SessionReplay
from voxforge.infrastructure.db.replay_repository import ReplayRepository


class ReplayService:
    def __init__(self, repository: ReplayRepository) -> None:
        self._repository = repository

    async def get_session_replay(
        self, session_id: UUID, *, org_id: UUID | None = None
    ) -> SessionReplay:
        return await self._repository.get_session_replay(session_id, org_id=org_id)
