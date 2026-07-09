from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.agent_config import PolicyPreset
from voxforge.infrastructure.db.models import SupportTemplateModel

BUILTIN_POLICY_PRESETS: list[PolicyPreset] = [
    PolicyPreset(
        slug="strict-compliance",
        name="Strict Compliance",
        description="Conservative policy-safe responses with a high quality bar and low escalation tolerance.",
        source="builtin",
        prompt_config={
            "system_prompt": (
                "You are a compliance-focused support voice agent. Follow policy exactly, "
                "avoid speculation, and escalate when uncertain."
            ),
            "style": "formal, policy-safe, verification-first",
        },
        orchestrator_config={"mode": "single", "max_agent_iterations": 1},
        eval_thresholds={
            "task_success_min": 0.85,
            "quality_min": 0.85,
            "escalation_max": 0.2,
        },
        tool_config={"fallback_to_human": True},
    ),
    PolicyPreset(
        slug="aggressive-deflection",
        name="Aggressive Deflection",
        description="Optimize for self-serve resolution with tighter escalation thresholds.",
        source="builtin",
        prompt_config={
            "system_prompt": (
                "You are a deflection-focused support voice agent. Resolve issues quickly "
                "using available tools before escalating."
            ),
            "style": "concise, action-oriented",
        },
        orchestrator_config={"mode": "single", "max_agent_iterations": 3},
        eval_thresholds={
            "task_success_min": 0.75,
            "quality_min": 0.7,
            "escalation_max": 0.25,
        },
        tool_config={"fallback_to_human": True},
    ),
    PolicyPreset(
        slug="high-touch-escalation",
        name="High-Touch Escalation",
        description="Prioritize empathetic handoff when confidence is moderate or risk is high.",
        source="builtin",
        prompt_config={
            "system_prompt": (
                "You are a high-touch support voice agent. Prioritize customer trust and "
                "escalate early when policy risk or frustration is detected."
            ),
            "style": "empathetic, escalation-ready",
        },
        orchestrator_config={"mode": "multi_agent", "max_agent_iterations": 2},
        eval_thresholds={
            "task_success_min": 0.8,
            "quality_min": 0.8,
            "escalation_max": 0.5,
        },
        tool_config={"fallback_to_human": True},
    ),
]


async def list_policy_presets(db: AsyncSession) -> list[PolicyPreset]:
    presets = {preset.slug: preset for preset in BUILTIN_POLICY_PRESETS}
    result = await db.execute(
        select(SupportTemplateModel).order_by(SupportTemplateModel.created_at.asc())
    )
    for template in result.scalars().all():
        presets[template.slug] = PolicyPreset(
            slug=template.slug,
            name=template.name,
            description=f"Support template: {template.name}",
            source="template",
            prompt_config=template.prompt_config or {},
            orchestrator_config={"mode": "single", "max_agent_iterations": 2},
            eval_thresholds=template.eval_thresholds or {},
            tool_config=template.tool_config or {},
        )
    return sorted(presets.values(), key=lambda preset: (preset.source, preset.name))


def get_policy_preset(presets: list[PolicyPreset], slug: str) -> PolicyPreset | None:
    for preset in presets:
        if preset.slug == slug:
            return preset
    return None
