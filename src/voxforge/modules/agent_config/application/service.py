from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.agent_config import AgentConfigVersion, PolicyPreset
from voxforge.infrastructure.db.agent_config_repository import (
    AgentConfigRepository,
    ConfigPresetNotFoundError,
)
from voxforge.infrastructure.db.models import SupportTemplateModel
from voxforge.modules.agent_config.application.presets import get_policy_preset, list_policy_presets


class AgentConfigService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AgentConfigRepository(db)

    async def list_versions(self, org_id: UUID, *, limit: int = 50) -> list[AgentConfigVersion]:
        return await self._repo.list_versions(org_id, limit=limit)

    async def get_active(self, org_id: UUID) -> AgentConfigVersion | None:
        return await self._repo.get_active(org_id)

    async def list_presets(self) -> list[PolicyPreset]:
        return await list_policy_presets(self._db)

    async def apply_preset(
        self,
        *,
        org_id: UUID,
        user_id: UUID | None,
        preset_slug: str,
        change_note: str | None = None,
        activate: bool = True,
    ) -> AgentConfigVersion:
        presets = await self.list_presets()
        preset = get_policy_preset(presets, preset_slug)
        if preset is None:
            raise ConfigPresetNotFoundError(preset_slug)
        note = change_note or f"Applied policy preset: {preset.name}"
        version = await self._repo.next_version_number(org_id)
        return await self._repo.create_version(
            org_id=org_id,
            version=version,
            label=f"preset:{preset.slug}",
            prompt_config=preset.prompt_config,
            orchestrator_config=preset.orchestrator_config,
            eval_thresholds=preset.eval_thresholds,
            created_by_user_id=user_id,
            change_note=note,
            activate=activate,
        )

    async def create_version(
        self,
        *,
        org_id: UUID,
        user_id: UUID | None,
        label: str,
        prompt_config: dict | None = None,
        orchestrator_config: dict | None = None,
        eval_thresholds: dict | None = None,
        change_note: str | None = None,
        activate: bool = True,
    ) -> AgentConfigVersion:
        defaults = await self._default_configs()
        version = await self._repo.next_version_number(org_id)
        return await self._repo.create_version(
            org_id=org_id,
            version=version,
            label=label,
            prompt_config=prompt_config or defaults["prompt_config"],
            orchestrator_config=orchestrator_config or defaults["orchestrator_config"],
            eval_thresholds=eval_thresholds or defaults["eval_thresholds"],
            created_by_user_id=user_id,
            change_note=change_note,
            activate=activate,
        )

    async def rollback(
        self,
        *,
        org_id: UUID,
        user_id: UUID | None,
        target_version: int,
        change_note: str | None = None,
    ) -> AgentConfigVersion:
        source = await self._repo.get_by_version(org_id, target_version)
        version = await self._repo.next_version_number(org_id)
        note = change_note or f"Rollback to version {target_version}"
        return await self._repo.create_version(
            org_id=org_id,
            version=version,
            label=f"rollback-from-v{target_version}",
            prompt_config=source.prompt_config,
            orchestrator_config=source.orchestrator_config,
            eval_thresholds=source.eval_thresholds,
            created_by_user_id=user_id,
            change_note=note,
            activate=True,
        )

    async def commit(self) -> None:
        await self._db.commit()

    async def _default_configs(self) -> dict[str, dict]:
        result = await self._db.execute(
            select(SupportTemplateModel)
            .where(SupportTemplateModel.is_default.is_(True))
            .order_by(SupportTemplateModel.created_at.asc())
            .limit(1)
        )
        template = result.scalar_one_or_none()
        if template is None:
            return {
                "prompt_config": {
                    "system_prompt": (
                        "You are a support voice agent focused on rapid resolution "
                        "and safe escalation."
                    )
                },
                "orchestrator_config": {"mode": "single", "max_agent_iterations": 2},
                "eval_thresholds": {
                    "task_success_min": 0.8,
                    "quality_min": 0.75,
                    "escalation_max": 0.35,
                },
            }
        return {
            "prompt_config": template.prompt_config or {},
            "orchestrator_config": {"mode": "single", "max_agent_iterations": 2},
            "eval_thresholds": template.eval_thresholds or {},
        }
