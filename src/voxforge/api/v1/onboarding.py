from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from voxforge.api.dependencies import (
    get_onboarding_pipeline_runner,
    get_onboarding_service,
    get_session_manager,
    rate_limit_category,
    require_scope,
)
from voxforge.core.domain.auth import Principal
from voxforge.infrastructure.voice.programmatic_runner import ProgrammaticPipelineRunner
from voxforge.modules.onboarding.application.service import OnboardingService
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingRunResponse(BaseModel):
    id: UUID
    status: str
    connected_at: str | None
    test_session_id: UUID | None
    completed_at: str | None


class ConnectTokenRequest(BaseModel):
    token_preview: str | None = None


@router.post("/start", response_model=OnboardingRunResponse)
async def onboarding_start(
    principal: Principal = Depends(require_scope("sessions:write")),
    onboarding: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingRunResponse:
    run = await onboarding.start(principal.org_id, principal.user_id)
    await onboarding.commit()
    return _run_response(run)


@router.post("/connect-token", response_model=OnboardingRunResponse)
async def onboarding_connect_token(
    body: ConnectTokenRequest,
    principal: Principal = Depends(require_scope("sessions:write")),
    onboarding: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingRunResponse:
    run = await onboarding.connect_token(
        principal.org_id,
        principal.user_id,
        token_preview=body.token_preview,
    )
    await onboarding.commit()
    return _run_response(run)


@router.post("/run-sample-call", response_model=OnboardingRunResponse)
async def onboarding_run_sample_call(
    principal: Principal = Depends(require_scope("sessions:write")),
    _: None = Depends(rate_limit_category("onboarding_sample")),
    onboarding: OnboardingService = Depends(get_onboarding_service),
    session_manager: SessionManager = Depends(get_session_manager),
    pipeline_runner: ProgrammaticPipelineRunner = Depends(get_onboarding_pipeline_runner),
) -> OnboardingRunResponse:
    run = await onboarding.run_sample_call(
        principal.org_id,
        principal.user_id,
        session_manager,
        pipeline_runner,
    )
    await onboarding.commit()
    return _run_response(run)


@router.get("/status", response_model=OnboardingRunResponse | None)
async def onboarding_status(
    principal: Principal = Depends(require_scope("sessions:read")),
    onboarding: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingRunResponse | None:
    run = await onboarding.status(principal.org_id)
    if run is None:
        return None
    return _run_response(run)


def _run_response(run) -> OnboardingRunResponse:
    return OnboardingRunResponse(
        id=run.id,
        status=run.status,
        connected_at=run.connected_at.isoformat() if run.connected_at else None,
        test_session_id=run.test_session_id,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
    )
