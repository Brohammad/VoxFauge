from typing import Protocol
from uuid import UUID

from voxforge.core.domain.entities import TurnMetrics


class OnboardingPipelineRunner(Protocol):
    """Port for running a scripted voice turn through the production pipeline."""

    async def run_scripted_turn(
        self,
        session_id: UUID,
        org_id: UUID,
        *,
        transcript: str,
        user_metadata: dict | None = None,
    ) -> TurnMetrics: ...
