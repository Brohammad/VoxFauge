"""Unit tests for turn handoff context builder."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.core.domain.evaluation import (
    EvaluationMetric,
    EvaluationRun,
    EvaluationStatus,
    MetricName,
)
from voxforge.core.domain.handoff import ConfidenceSignals
from voxforge.modules.handoff.application.context import build_turn_handoff_context


class TestBuildTurnHandoffContext:
    def test_minimal_context(self):
        ctx = build_turn_handoff_context(
            user_transcript="Hello",
            assistant_response="Hi there",
            interrupted=False,
            confidence=0.9,
            agent_trace=None,
            evaluation_run=None,
            consecutive_tool_failures=0,
        )
        assert ctx.user_transcript == "Hello"
        assert ctx.assistant_response == "Hi there"
        assert ctx.interrupted is False
        assert ctx.confidence_signals.stt_confidence == 0.9
        assert ctx.tool_failures_this_turn == 0
        assert ctx.failed_tools == []
        assert ctx.critical_tool_failed is False

    def test_tool_failures_detected(self):
        trace = [
            {"agent": "tool", "tool": "ticket_lookup", "status": "error"},
            {"agent": "tool", "tool": "knowledge_base_lookup", "status": "completed"},
            {"agent": "tool", "tool": "create_ticket", "status": "timeout"},
        ]
        ctx = build_turn_handoff_context(
            user_transcript="Help me",
            assistant_response="Trying...",
            interrupted=False,
            confidence=None,
            agent_trace=trace,
            evaluation_run=None,
            consecutive_tool_failures=2,
        )
        assert ctx.tool_failures_this_turn == 2
        assert "ticket_lookup" in ctx.failed_tools
        assert "create_ticket" in ctx.failed_tools
        assert ctx.critical_tool_failed is True
        assert ctx.confidence_signals.tool_success_ratio == pytest.approx(1 / 3)

    def test_critic_approved_from_trace(self):
        trace = [{"agent": "critic", "status": "approved", "summary": "ok"}]
        ctx = build_turn_handoff_context(
            user_transcript="x",
            assistant_response="y",
            interrupted=False,
            confidence=None,
            agent_trace=trace,
            evaluation_run=None,
            consecutive_tool_failures=0,
        )
        assert ctx.confidence_signals.critic_approved is True

    def test_hallucination_score_from_evaluation(self):
        run = EvaluationRun(
            id=uuid4(),
            org_id=uuid4(),
            session_id=uuid4(),
            user_transcript="q",
            assistant_response="a",
            overall_score=0.8,
            overall_status=EvaluationStatus.PASSED,
            metrics=[
                EvaluationMetric(
                    name=MetricName.HALLUCINATION,
                    score=0.15,
                    status=EvaluationStatus.PASSED,
                ),
            ],
            created_at=datetime.now(UTC),
        )
        ctx = build_turn_handoff_context(
            user_transcript="q",
            assistant_response="a",
            interrupted=False,
            confidence=None,
            agent_trace=None,
            evaluation_run=run,
            consecutive_tool_failures=0,
        )
        assert ctx.confidence_signals.hallucination_score == 0.15

    def test_kb_similarity_from_tool_payload(self):
        trace = [
            {
                "agent": "tool",
                "tool": "knowledge_base_lookup",
                "status": "completed",
                "payload": {"top_similarity": 0.87},
            }
        ]
        ctx = build_turn_handoff_context(
            user_transcript="refund?",
            assistant_response="policy...",
            interrupted=False,
            confidence=None,
            agent_trace=trace,
            evaluation_run=None,
            consecutive_tool_failures=0,
        )
        assert ctx.confidence_signals.kb_top_similarity == 0.87

    def test_interrupted_flag(self):
        ctx = build_turn_handoff_context(
            user_transcript="stop",
            assistant_response="",
            interrupted=True,
            confidence=0.5,
            agent_trace=None,
            evaluation_run=None,
            consecutive_tool_failures=0,
        )
        assert ctx.interrupted is True
