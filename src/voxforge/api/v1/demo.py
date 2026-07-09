"""Public demo endpoints for the hosted experience."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from voxforge.api.dependencies import (
    get_onboarding_pipeline_runner,
    get_onboarding_service,
    get_session_manager,
)
from voxforge.config import Settings, get_settings
from voxforge.infrastructure.voice.programmatic_runner import ProgrammaticPipelineRunner
from voxforge.modules.onboarding.application.sample_scripts import get_default_sample_script
from voxforge.modules.onboarding.application.service import OnboardingService
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoQuickstartResponse(BaseModel):
    status: str
    session_id: UUID | None = None
    user_transcript: str
    assistant_response: str | None = None
    e2e_ms: float | None = None
    script_id: str


class DemoAccountResponse(BaseModel):
    email: str
    password_hint: str
    org_name: str
    note: str


@router.get("/info", response_model=DemoAccountResponse)
async def demo_info(settings: Settings = Depends(get_settings)) -> DemoAccountResponse:
    if not settings.demo_enabled:
        raise HTTPException(status_code=404, detail="Demo is not enabled")
    return DemoAccountResponse(
        email=settings.demo_email,
        password_hint=settings.demo_password_hint,
        org_name="VoxForge Demo",
        note="Use POST /api/v1/demo/quickstart for a one-click pipeline experience, "
        "or log in with the demo account to explore the dashboard.",
    )


@router.post("/quickstart", response_model=DemoQuickstartResponse)
async def demo_quickstart(
    settings: Settings = Depends(get_settings),
    onboarding: OnboardingService = Depends(get_onboarding_service),
    session_manager: SessionManager = Depends(get_session_manager),
    pipeline_runner: ProgrammaticPipelineRunner = Depends(get_onboarding_pipeline_runner),
) -> DemoQuickstartResponse:
    """Run the production voice pipeline demo without authentication (rate limited)."""
    if not settings.demo_enabled:
        raise HTTPException(status_code=404, detail="Demo is not enabled")

    org_id = UUID(settings.demo_org_id)
    user_id = UUID(settings.demo_user_id)
    script = get_default_sample_script()

    run = await onboarding.run_sample_call(
        org_id,
        user_id,
        session_manager,
        pipeline_runner,
    )
    await onboarding.commit()

    metadata = run.metadata_ or {}
    assistant_response: str | None = None
    if run.test_session_id:
        messages = await session_manager.get_messages(run.test_session_id)
        for message in reversed(messages):
            if message.role.value == "assistant":
                assistant_response = message.content
                break

    return DemoQuickstartResponse(
        status=run.status,
        session_id=run.test_session_id,
        user_transcript=script.user_transcript,
        assistant_response=assistant_response,
        e2e_ms=metadata.get("e2e_ms"),
        script_id=script.script_id,
    )
