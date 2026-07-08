from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from voxforge.api.dependencies import get_onboarding_service, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.modules.onboarding.application.service import OnboardingService

router = APIRouter(prefix="/templates", tags=["templates"])


class SupportTemplateResponse(BaseModel):
    name: str
    slug: str
    prompt_config: dict
    tool_config: dict
    eval_thresholds: dict
    is_default: bool


@router.get("/support/default", response_model=SupportTemplateResponse)
async def get_default_support_template(
    _principal: Principal = Depends(require_scope("sessions:read")),
    onboarding: OnboardingService = Depends(get_onboarding_service),
) -> SupportTemplateResponse:
    template = await onboarding.get_default_template()
    if template is None:
        raise HTTPException(status_code=404, detail="Default support template not found")
    return SupportTemplateResponse(
        name=template.name,
        slug=template.slug,
        prompt_config=template.prompt_config,
        tool_config=template.tool_config,
        eval_thresholds=template.eval_thresholds,
        is_default=template.is_default,
    )
