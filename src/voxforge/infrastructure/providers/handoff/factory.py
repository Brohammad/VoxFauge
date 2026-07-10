"""Assignment provider factory."""

from voxforge.config import Settings
from voxforge.core.interfaces.handoff import AssignmentProvider
from voxforge.infrastructure.db.handoff_repository import HandoffRepository
from voxforge.infrastructure.providers.handoff.mock_assignment import MockAssignmentProvider
from voxforge.infrastructure.providers.handoff.round_robin import RoundRobinAssignmentProvider


def create_assignment_provider(
    settings: Settings,
    repository: HandoffRepository,
) -> AssignmentProvider:
    provider = settings.handoff_assignment_provider.lower()
    if provider == "round_robin":
        return RoundRobinAssignmentProvider(repository._session)
    return MockAssignmentProvider()
