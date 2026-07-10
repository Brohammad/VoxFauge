"""Build TurnHandoffContext from voice pipeline turn data."""

from __future__ import annotations

from voxforge.core.domain.evaluation import EvaluationRun, MetricName
from voxforge.core.domain.handoff import ConfidenceSignals, TurnHandoffContext
from voxforge.modules.handoff.application.policy import CRITICAL_TOOLS


def build_turn_handoff_context(
    *,
    user_transcript: str,
    assistant_response: str,
    interrupted: bool,
    confidence: float | None,
    agent_trace: list[dict] | None,
    evaluation_run: EvaluationRun | None,
    consecutive_tool_failures: int,
) -> TurnHandoffContext:
    trace = agent_trace or []
    tool_steps = [s for s in trace if s.get("agent") == "tool"]
    failed_tools: list[str] = []
    tool_failures_this_turn = 0
    for step in tool_steps:
        status = str(step.get("status", "")).lower()
        tool_name = str(step.get("tool") or step.get("summary") or "unknown")
        if status in ("error", "timeout", "failed"):
            tool_failures_this_turn += 1
            failed_tools.append(tool_name)

    total_tools = len(tool_steps)
    successful = sum(
        1 for s in tool_steps if str(s.get("status", "")).lower() in ("completed", "success", "ok")
    )
    tool_success_ratio = successful / total_tools if total_tools else None

    critic_step = next((s for s in trace if s.get("agent") == "critic"), None)
    critic_approved = None
    if critic_step is not None:
        critic_approved = str(critic_step.get("status", "")).lower() in (
            "completed",
            "approved",
            "success",
        )

    hallucination_score = None
    if evaluation_run is not None:
        for metric in evaluation_run.metrics:
            if metric.name == MetricName.HALLUCINATION:
                hallucination_score = metric.score
                break

    kb_similarity = None
    for step in tool_steps:
        if step.get("tool") == "knowledge_base_lookup" and step.get("status") == "completed":
            payload = step.get("payload") or {}
            if isinstance(payload, dict) and payload.get("top_similarity") is not None:
                kb_similarity = float(payload["top_similarity"])

    critical_tool_failed = any(
        name in CRITICAL_TOOLS for name in failed_tools
    )

    return TurnHandoffContext(
        user_transcript=user_transcript,
        assistant_response=assistant_response,
        interrupted=interrupted,
        confidence_signals=ConfidenceSignals(
            critic_approved=critic_approved,
            hallucination_score=hallucination_score,
            tool_success_ratio=tool_success_ratio,
            stt_confidence=confidence,
            kb_top_similarity=kb_similarity,
        ),
        tool_failures_this_turn=tool_failures_this_turn,
        consecutive_tool_failures=consecutive_tool_failures,
        failed_tools=failed_tools,
        critical_tool_failed=critical_tool_failed,
    )
