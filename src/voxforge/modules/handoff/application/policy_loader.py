"""Load escalation policy from session config and application settings."""

from __future__ import annotations

from voxforge.config import Settings
from voxforge.core.domain.handoff import AssignmentStrategy, EscalationPolicy


def load_escalation_policy(config: dict, settings: Settings) -> EscalationPolicy:
    tool_config = config.get("tool_config", {})
    if not isinstance(tool_config, dict):
        tool_config = {}

    strategy_raw = config.get("assignment_strategy") or tool_config.get(
        "assignment_strategy", "round_robin"
    )
    try:
        strategy = AssignmentStrategy(str(strategy_raw))
    except ValueError:
        strategy = AssignmentStrategy.ROUND_ROBIN

    return EscalationPolicy(
        fallback_to_human=bool(
            config.get("fallback_to_human", tool_config.get("fallback_to_human", True))
        ),
        min_confidence=float(config.get("min_confidence", settings.handoff_min_confidence)),
        escalate_on_tool_failure=bool(
            config.get(
                "escalate_on_tool_failure",
                settings.handoff_escalate_on_tool_failure,
            )
        ),
        max_tool_failures=int(config.get("max_tool_failures", settings.handoff_max_tool_failures)),
        escalate_on_critical_tool_failure=bool(
            config.get("escalate_on_critical_tool_failure", True)
        ),
        require_explicit_request=bool(config.get("require_explicit_request", False)),
        auto_create_ticket=bool(config.get("auto_create_ticket", True)),
        assignment_strategy=strategy,
        handoff_message=str(
            config.get(
                "handoff_message",
                EscalationPolicy().handoff_message,
            )
        ),
    )
