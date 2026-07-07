from voxforge.config import Settings
from voxforge.core.domain.evaluation import (
    EvaluationMetric,
    EvaluationStatus,
    MetricName,
    TurnEvaluationInput,
)


def _status_from_score(score: float) -> EvaluationStatus:
    if score >= 0.8:
        return EvaluationStatus.PASSED
    if score >= 0.5:
        return EvaluationStatus.WARNING
    return EvaluationStatus.FAILED


class LatencyEvaluator:
    name = MetricName.LATENCY.value

    def __init__(self, settings: Settings) -> None:
        self._target_ms = settings.evaluation_e2e_target_ms

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        e2e = turn.e2e_ms
        if e2e is None:
            return EvaluationMetric(
                name=MetricName.LATENCY,
                score=0.0,
                status=EvaluationStatus.FAILED,
                details={"reason": "no e2e measurement"},
            )

        score = max(0.0, min(1.0, 1.0 - (e2e - self._target_ms) / self._target_ms))
        if e2e <= self._target_ms:
            score = 1.0

        return EvaluationMetric(
            name=MetricName.LATENCY,
            score=round(score, 3),
            value=e2e,
            unit="ms",
            status=_status_from_score(score),
            details={
                "stt_ms": turn.stt_ms,
                "llm_first_token_ms": turn.llm_first_token_ms,
                "tts_first_byte_ms": turn.tts_first_byte_ms,
                "target_ms": self._target_ms,
            },
        )


class TaskCompletionEvaluator:
    name = MetricName.TASK_COMPLETION.value

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        if turn.interrupted:
            score = 0.3
        elif turn.assistant_response.strip():
            score = 1.0
        else:
            score = 0.0

        return EvaluationMetric(
            name=MetricName.TASK_COMPLETION,
            score=score,
            status=_status_from_score(score),
            details={"interrupted": turn.interrupted},
        )


class ToolAccuracyEvaluator:
    name = MetricName.TOOL_ACCURACY.value

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        if not turn.tool_calls:
            return EvaluationMetric(
                name=MetricName.TOOL_ACCURACY,
                score=1.0,
                status=EvaluationStatus.PASSED,
                details={"tool_calls": 0},
            )

        successes = sum(1 for tc in turn.tool_calls if tc.get("status") == "success")
        score = successes / len(turn.tool_calls)

        return EvaluationMetric(
            name=MetricName.TOOL_ACCURACY,
            score=round(score, 3),
            value=float(len(turn.tool_calls)),
            unit="calls",
            status=_status_from_score(score),
            details={"successes": successes, "total": len(turn.tool_calls)},
        )


class ConversationQualityEvaluator:
    name = MetricName.CONVERSATION_QUALITY.value

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        response = turn.assistant_response.strip()
        if not response:
            score = 0.0
        elif len(response) < 5:
            score = 0.4
        elif len(response) > 2000:
            score = 0.6
        else:
            score = 1.0

        return EvaluationMetric(
            name=MetricName.CONVERSATION_QUALITY,
            score=score,
            value=float(len(response)),
            unit="chars",
            status=_status_from_score(score),
            details={"response_length": len(response)},
        )


class CostEvaluator:
    name = MetricName.COST.value

    def __init__(self, settings: Settings) -> None:
        self._input_cost = settings.evaluation_llm_input_cost_per_1k
        self._output_cost = settings.evaluation_llm_output_cost_per_1k
        self._budget_usd = settings.evaluation_turn_cost_budget_usd

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        input_tokens = turn.estimated_input_tokens or _estimate_tokens(turn.user_transcript)
        output_tokens = turn.estimated_output_tokens or _estimate_tokens(turn.assistant_response)
        cost_usd = (input_tokens / 1000 * self._input_cost) + (
            output_tokens / 1000 * self._output_cost
        )
        score = max(0.0, min(1.0, 1.0 - cost_usd / self._budget_usd))

        return EvaluationMetric(
            name=MetricName.COST,
            score=round(score, 3),
            value=round(cost_usd, 6),
            unit="usd",
            status=_status_from_score(score),
            details={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "budget_usd": self._budget_usd,
            },
        )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
