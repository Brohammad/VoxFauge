"""Handoff policy engine and user request detection."""

from __future__ import annotations

from voxforge.core.domain.handoff import (
    ConfidenceSignals,
    EscalationPolicy,
    HandoffDecision,
    HandoffTrigger,
    TurnHandoffContext,
)

CRITICAL_TOOLS = frozenset({"knowledge_base_lookup", "ticket_lookup", "handoff_to_human"})

DEFAULT_SIGNAL_WEIGHTS: dict[str, float] = {
    "critic_approved": 0.30,
    "hallucination_score": 0.25,
    "tool_success_ratio": 0.20,
    "stt_confidence": 0.15,
    "kb_top_similarity": 0.10,
}

EXPLICIT_HUMAN_PHRASES = (
    "speak to a human",
    "talk to a human",
    "real person",
    "live agent",
    "human agent",
    "representative",
    "operator",
)

TRANSFER_PHRASES = (
    "transfer me",
    "escalate",
    "handoff",
    "hand off",
)

FRUSTRATION_PHRASES = (
    "this isn't working",
    "this is not working",
    "i've tried everything",
    "useless",
    "frustrated",
)


class UserRequestDetector:
    """Detect explicit or implicit user requests for human assistance."""

    def detect(self, transcript: str, *, require_explicit: bool = False) -> tuple[bool, str]:
        text = transcript.lower().strip()
        if not text:
            return False, ""

        for phrase in EXPLICIT_HUMAN_PHRASES:
            if phrase in text:
                return True, f"explicit request: '{phrase}'"

        if require_explicit:
            return False, ""

        for phrase in TRANSFER_PHRASES:
            if phrase in text:
                return True, f"transfer request: '{phrase}'"

        for phrase in FRUSTRATION_PHRASES:
            if phrase in text:
                return True, f"frustration signal: '{phrase}'"

        return False, ""


def compute_confidence_score(
    signals: ConfidenceSignals,
    weights: dict[str, float] | None = None,
) -> float | None:
    """Compute weighted composite confidence from available signals."""
    w = weights or DEFAULT_SIGNAL_WEIGHTS
    components: list[tuple[float, float]] = []

    if signals.critic_approved is not None:
        components.append((1.0 if signals.critic_approved else 0.0, w["critic_approved"]))

    if signals.hallucination_score is not None:
        components.append((signals.hallucination_score, w["hallucination_score"]))

    if signals.tool_success_ratio is not None:
        components.append((signals.tool_success_ratio, w["tool_success_ratio"]))

    if signals.stt_confidence is not None:
        components.append((signals.stt_confidence, w["stt_confidence"]))

    if signals.kb_top_similarity is not None:
        components.append((signals.kb_top_similarity, w["kb_top_similarity"]))

    if not components:
        return None

    total_weight = sum(weight for _, weight in components)
    if total_weight == 0:
        return None

    return sum(value * weight for value, weight in components) / total_weight


class HandoffPolicyEngine:
    """Evaluate escalation triggers against org policy."""

    def __init__(self, user_detector: UserRequestDetector | None = None) -> None:
        self._user_detector = user_detector or UserRequestDetector()

    def evaluate(
        self,
        context: TurnHandoffContext,
        policy: EscalationPolicy,
    ) -> HandoffDecision:
        if not policy.fallback_to_human:
            return HandoffDecision(should_escalate=False, reason="fallback_to_human disabled")

        confidence = compute_confidence_score(context.confidence_signals)

        # Priority order: user request > tool failure > confidence threshold
        user_requested, user_reason = self._user_detector.detect(
            context.user_transcript,
            require_explicit=policy.require_explicit_request,
        )
        if user_requested:
            return HandoffDecision(
                should_escalate=True,
                trigger=HandoffTrigger.USER_REQUEST,
                confidence=confidence,
                reason=user_reason,
            )

        if policy.escalate_on_critical_tool_failure and context.critical_tool_failed:
            tools = ", ".join(context.failed_tools) or "critical tool"
            return HandoffDecision(
                should_escalate=True,
                trigger=HandoffTrigger.TOOL_FAILURE,
                confidence=confidence,
                reason=f"critical tool failure: {tools}",
            )

        if policy.escalate_on_tool_failure:
            if context.tool_failures_this_turn > 0:
                tools = ", ".join(context.failed_tools) or "unknown tool"
                return HandoffDecision(
                    should_escalate=True,
                    trigger=HandoffTrigger.TOOL_FAILURE,
                    confidence=confidence,
                    reason=f"tool failure this turn: {tools}",
                )
            if context.consecutive_tool_failures >= policy.max_tool_failures:
                return HandoffDecision(
                    should_escalate=True,
                    trigger=HandoffTrigger.TOOL_FAILURE,
                    confidence=confidence,
                    reason=(
                        f"consecutive tool failures ({context.consecutive_tool_failures}"
                        f" >= {policy.max_tool_failures})"
                    ),
                )

        if confidence is not None and confidence < policy.min_confidence:
            return HandoffDecision(
                should_escalate=True,
                trigger=HandoffTrigger.CONFIDENCE_THRESHOLD,
                confidence=confidence,
                reason=(
                    f"confidence {confidence:.2f} below threshold {policy.min_confidence:.2f}"
                ),
            )

        if context.interrupted:
            return HandoffDecision(
                should_escalate=True,
                trigger=HandoffTrigger.POLICY,
                confidence=confidence,
                reason="user interrupted turn",
            )

        return HandoffDecision(
            should_escalate=False,
            confidence=confidence,
            reason="no escalation triggers matched",
        )
