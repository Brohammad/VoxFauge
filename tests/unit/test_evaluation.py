"""Unit tests for evaluation evaluators."""

from uuid import uuid4

from voxforge.config import Settings
from voxforge.core.domain.evaluation import EvaluationStatus, TurnEvaluationInput
from voxforge.modules.evaluation.application.evaluators import (
    ConversationQualityEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    TaskCompletionEvaluator,
    ToolAccuracyEvaluator,
)


def _turn(**kwargs) -> TurnEvaluationInput:
    defaults = {
        "session_id": uuid4(),
        "user_transcript": "What is 2 plus 2?",
        "assistant_response": "That equals four.",
        "e2e_ms": 1500.0,
    }
    defaults.update(kwargs)
    return TurnEvaluationInput(**defaults)


def test_latency_evaluator_passes_under_target():
    ev = LatencyEvaluator(Settings(evaluation_e2e_target_ms=2000))
    metric = ev.evaluate(_turn(e2e_ms=1500))
    assert metric.status == EvaluationStatus.PASSED
    assert metric.score == 1.0


def test_latency_evaluator_fails_without_measurement():
    ev = LatencyEvaluator(Settings())
    metric = ev.evaluate(_turn(e2e_ms=None))
    assert metric.status == EvaluationStatus.FAILED


def test_task_completion_with_response():
    metric = TaskCompletionEvaluator().evaluate(_turn())
    assert metric.score == 1.0


def test_task_completion_interrupted():
    metric = TaskCompletionEvaluator().evaluate(_turn(interrupted=True))
    assert metric.score < 1.0


def test_tool_accuracy_no_calls():
    metric = ToolAccuracyEvaluator().evaluate(_turn())
    assert metric.score == 1.0


def test_tool_accuracy_partial_success():
    metric = ToolAccuracyEvaluator().evaluate(
        _turn(tool_calls=[{"status": "success"}, {"status": "error"}])
    )
    assert metric.score == 0.5


def test_conversation_quality_empty_response():
    metric = ConversationQualityEvaluator().evaluate(_turn(assistant_response=""))
    assert metric.score == 0.0


def test_cost_evaluator():
    metric = CostEvaluator(Settings()).evaluate(
        _turn(estimated_input_tokens=100, estimated_output_tokens=50)
    )
    assert metric.value is not None
    assert metric.unit == "usd"
