"""Unit tests for handoff policy engine and user request detection."""

import pytest

from voxforge.core.domain.handoff import (
    ConfidenceSignals,
    EscalationPolicy,
    HandoffTrigger,
    TurnHandoffContext,
)
from voxforge.modules.handoff.application.policy import (
    HandoffPolicyEngine,
    UserRequestDetector,
    compute_confidence_score,
)


@pytest.fixture
def engine():
    return HandoffPolicyEngine()


@pytest.fixture
def default_policy():
    return EscalationPolicy()


class TestUserRequestDetector:
    def test_explicit_human_request(self):
        detector = UserRequestDetector()
        detected, reason = detector.detect("I need to speak to a human please")
        assert detected is True
        assert "explicit request" in reason

    def test_transfer_request(self):
        detector = UserRequestDetector()
        detected, reason = detector.detect("Can you transfer me to someone?")
        assert detected is True
        assert "transfer request" in reason

    def test_frustration_when_not_require_explicit(self):
        detector = UserRequestDetector()
        detected, _ = detector.detect("This isn't working at all")
        assert detected is True

    def test_frustration_ignored_when_require_explicit(self):
        detector = UserRequestDetector()
        detected, _ = detector.detect("This isn't working", require_explicit=True)
        assert detected is False

    def test_no_request(self):
        detector = UserRequestDetector()
        detected, reason = detector.detect("What is your refund policy?")
        assert detected is False
        assert reason == ""


class TestConfidenceScore:
    def test_weighted_composite(self):
        signals = ConfidenceSignals(
            critic_approved=True,
            hallucination_score=0.9,
            tool_success_ratio=1.0,
            stt_confidence=0.95,
            kb_top_similarity=0.8,
        )
        score = compute_confidence_score(signals)
        assert score is not None
        assert 0.85 <= score <= 0.95

    def test_low_confidence_signals(self):
        signals = ConfidenceSignals(
            critic_approved=False,
            hallucination_score=0.3,
            tool_success_ratio=0.0,
        )
        score = compute_confidence_score(signals)
        assert score is not None
        assert score < 0.4

    def test_no_signals_returns_none(self):
        assert compute_confidence_score(ConfidenceSignals()) is None


class TestHandoffPolicyEngine:
    def test_user_request_triggers_escalation(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Let me talk to a real person",
            confidence_signals=ConfidenceSignals(critic_approved=True, hallucination_score=0.9),
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.USER_REQUEST

    def test_confidence_below_threshold(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="What are your hours?",
            confidence_signals=ConfidenceSignals(
                critic_approved=False,
                hallucination_score=0.2,
                tool_success_ratio=0.0,
            ),
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.CONFIDENCE_THRESHOLD
        assert decision.confidence is not None
        assert decision.confidence < default_policy.min_confidence

    def test_tool_failure_this_turn(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Look up my ticket",
            tool_failures_this_turn=1,
            failed_tools=["ticket_lookup"],
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.TOOL_FAILURE

    def test_consecutive_tool_failures(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Try again",
            consecutive_tool_failures=2,
            failed_tools=["knowledge_base_lookup"],
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.TOOL_FAILURE

    def test_critical_tool_failure(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Search the knowledge base",
            critical_tool_failed=True,
            failed_tools=["knowledge_base_lookup"],
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.TOOL_FAILURE

    def test_high_confidence_no_escalation(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="How do I reset my password?",
            assistant_response="I can help you reset your password right now.",
            confidence_signals=ConfidenceSignals(
                critic_approved=True,
                hallucination_score=0.95,
                tool_success_ratio=1.0,
                stt_confidence=0.98,
            ),
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is False

    def test_fallback_disabled(self, engine):
        policy = EscalationPolicy(fallback_to_human=False)
        context = TurnHandoffContext(user_transcript="I want a human agent now")
        decision = engine.evaluate(context, policy)
        assert decision.should_escalate is False

    def test_strict_policy_requires_explicit_request(self, engine):
        policy = EscalationPolicy(require_explicit_request=True, min_confidence=0.9)
        context = TurnHandoffContext(
            user_transcript="This isn't working",
            confidence_signals=ConfidenceSignals(hallucination_score=0.1),
        )
        decision = engine.evaluate(context, policy)
        # Frustration ignored; confidence triggers instead
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.CONFIDENCE_THRESHOLD

    def test_interrupted_turn_escalates(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Wait stop",
            interrupted=True,
            confidence_signals=ConfidenceSignals(critic_approved=True, hallucination_score=0.9),
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.should_escalate is True
        assert decision.trigger == HandoffTrigger.POLICY

    def test_user_request_takes_priority_over_confidence(self, engine, default_policy):
        context = TurnHandoffContext(
            user_transcript="Transfer me to a human agent",
            confidence_signals=ConfidenceSignals(
                critic_approved=True,
                hallucination_score=0.99,
            ),
        )
        decision = engine.evaluate(context, default_policy)
        assert decision.trigger == HandoffTrigger.USER_REQUEST
