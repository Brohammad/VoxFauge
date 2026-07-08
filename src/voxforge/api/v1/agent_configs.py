from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from voxforge.api.dependencies import get_agent_config_service, require_scope
from voxforge.core.domain.agent_config import AgentConfigVersion
from voxforge.core.domain.auth import Principal
from voxforge.infrastructure.db.agent_config_repository import ConfigVersionNotFoundError
from voxforge.modules.agent_config.application.service import AgentConfigService

router = APIRouter(prefix="/agent-configs", tags=["agent-configs"])


class AgentConfigVersionResponse(BaseModel):
    id: UUID
    org_id: UUID
    version: int
    label: str
    prompt_config: dict
    orchestrator_config: dict
    eval_thresholds: dict
    is_active: bool
    created_by_user_id: UUID | None
    change_note: str | None
    created_at: str


class CreateAgentConfigRequest(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    prompt_config: dict | None = None
    orchestrator_config: dict | None = None
    eval_thresholds: dict | None = None
    change_note: str | None = None
    activate: bool = True


class RollbackAgentConfigRequest(BaseModel):
    target_version: int = Field(ge=1)
    change_note: str | None = None


@router.get("", response_model=list[AgentConfigVersionResponse])
async def list_agent_configs(
    limit: int = Query(50, ge=1, le=100),
    principal: Principal = Depends(require_scope("sessions:read")),
    service: AgentConfigService = Depends(get_agent_config_service),
) -> list[AgentConfigVersionResponse]:
    versions = await service.list_versions(principal.org_id, limit=limit)
    return [_to_response(item) for item in versions]


@router.get("/active", response_model=AgentConfigVersionResponse | None)
async def get_active_agent_config(
    principal: Principal = Depends(require_scope("sessions:read")),
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfigVersionResponse | None:
    active = await service.get_active(principal.org_id)
    return _to_response(active) if active else None


@router.post("", response_model=AgentConfigVersionResponse, status_code=201)
async def create_agent_config(
    body: CreateAgentConfigRequest,
    principal: Principal = Depends(require_scope("sessions:write")),
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfigVersionResponse:
    version = await service.create_version(
        org_id=principal.org_id,
        user_id=principal.user_id,
        label=body.label,
        prompt_config=body.prompt_config,
        orchestrator_config=body.orchestrator_config,
        eval_thresholds=body.eval_thresholds,
        change_note=body.change_note,
        activate=body.activate,
    )
    await service.commit()
    return _to_response(version)


@router.post("/rollback", response_model=AgentConfigVersionResponse)
async def rollback_agent_config(
    body: RollbackAgentConfigRequest,
    principal: Principal = Depends(require_scope("sessions:write")),
    service: AgentConfigService = Depends(get_agent_config_service),
) -> AgentConfigVersionResponse:
    try:
        version = await service.rollback(
            org_id=principal.org_id,
            user_id=principal.user_id,
            target_version=body.target_version,
            change_note=body.change_note,
        )
    except ConfigVersionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from None
    await service.commit()
    return _to_response(version)


def _to_response(item: AgentConfigVersion) -> AgentConfigVersionResponse:
    return AgentConfigVersionResponse(
        id=item.id,
        org_id=item.org_id,
        version=item.version,
        label=item.label,
        prompt_config=item.prompt_config,
        orchestrator_config=item.orchestrator_config,
        eval_thresholds=item.eval_thresholds,
        is_active=item.is_active,
        created_by_user_id=item.created_by_user_id,
        change_note=item.change_note,
        created_at=_iso(item.created_at),
    )


def _iso(value: datetime) -> str:
    return value.isoformat()
