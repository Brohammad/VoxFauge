from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.agent_config import AgentConfigVersion
from voxforge.core.exceptions import VoxForgeError
from voxforge.infrastructure.db.models import AgentConfigVersionModel


class ConfigVersionNotFoundError(VoxForgeError):
    def __init__(self, version: int) -> None:
        super().__init__(
            f"Config version {version} not found",
            code="config_version_not_found",
        )


class AgentConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_versions(self, org_id: UUID, *, limit: int = 50) -> list[AgentConfigVersion]:
        result = await self._session.execute(
            select(AgentConfigVersionModel)
            .where(AgentConfigVersionModel.org_id == org_id)
            .order_by(AgentConfigVersionModel.version.desc())
            .limit(limit)
        )
        return [self._to_entity(model) for model in result.scalars().all()]

    async def get_active(self, org_id: UUID) -> AgentConfigVersion | None:
        result = await self._session.execute(
            select(AgentConfigVersionModel)
            .where(
                AgentConfigVersionModel.org_id == org_id,
                AgentConfigVersionModel.is_active.is_(True),
            )
            .order_by(AgentConfigVersionModel.version.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_version(self, org_id: UUID, version: int) -> AgentConfigVersion:
        result = await self._session.execute(
            select(AgentConfigVersionModel).where(
                AgentConfigVersionModel.org_id == org_id,
                AgentConfigVersionModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise ConfigVersionNotFoundError(version)
        return self._to_entity(model)

    async def next_version_number(self, org_id: UUID) -> int:
        result = await self._session.execute(
            select(func.max(AgentConfigVersionModel.version)).where(
                AgentConfigVersionModel.org_id == org_id
            )
        )
        current = result.scalar_one()
        return int(current or 0) + 1

    async def deactivate_all(self, org_id: UUID) -> None:
        await self._session.execute(
            update(AgentConfigVersionModel)
            .where(AgentConfigVersionModel.org_id == org_id)
            .values(is_active=False)
        )

    async def create_version(
        self,
        *,
        org_id: UUID,
        version: int,
        label: str,
        prompt_config: dict,
        orchestrator_config: dict,
        eval_thresholds: dict,
        created_by_user_id: UUID | None,
        change_note: str | None,
        activate: bool,
    ) -> AgentConfigVersion:
        if activate:
            await self.deactivate_all(org_id)
        model = AgentConfigVersionModel(
            org_id=org_id,
            version=version,
            label=label,
            prompt_config=prompt_config,
            orchestrator_config=orchestrator_config,
            eval_thresholds=eval_thresholds,
            is_active=activate,
            created_by_user_id=created_by_user_id,
            change_note=change_note,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: AgentConfigVersionModel) -> AgentConfigVersion:
        return AgentConfigVersion(
            id=model.id,
            org_id=model.org_id,
            version=model.version,
            label=model.label,
            prompt_config=model.prompt_config or {},
            orchestrator_config=model.orchestrator_config or {},
            eval_thresholds=model.eval_thresholds or {},
            is_active=model.is_active,
            created_by_user_id=model.created_by_user_id,
            change_note=model.change_note,
            created_at=model.created_at,
        )
