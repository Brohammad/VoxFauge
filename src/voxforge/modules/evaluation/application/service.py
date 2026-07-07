from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.evaluation import (
    EvaluationMetric,
    EvaluationRun,
    EvaluationStatus,
    TurnEvaluationInput,
)
from voxforge.infrastructure.db.evaluation_repository import EvaluationRepository
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    evaluation_runs_total,
    evaluation_score_histogram,
)
from voxforge.modules.evaluation.application.evaluators import (
    ConversationQualityEvaluator,
    CostEvaluator,
    LatencyEvaluator,
    TaskCompletionEvaluator,
    ToolAccuracyEvaluator,
)

logger = get_logger(__name__)


class EvaluationEngine:
    """Scores each conversation turn across latency, quality, tools, and cost."""

    def __init__(self, repository: EvaluationRepository, settings: Settings) -> None:
        self._repo = repository
        self._settings = settings
        self._evaluators = [
            LatencyEvaluator(settings),
            TaskCompletionEvaluator(),
            ToolAccuracyEvaluator(),
            ConversationQualityEvaluator(),
            CostEvaluator(settings),
        ]

    async def evaluate_turn(self, turn: TurnEvaluationInput) -> EvaluationRun | None:
        if not self._settings.evaluation_enabled:
            return None

        metrics: list[EvaluationMetric] = [e.evaluate(turn) for e in self._evaluators]
        overall_score = round(sum(m.score for m in metrics) / len(metrics), 3)
        overall_status = _overall_status(metrics)

        run = await self._repo.save_run(
            org_id=turn.org_id,
            session_id=turn.session_id,
            user_transcript=turn.user_transcript,
            assistant_response=turn.assistant_response,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
        )

        evaluation_runs_total.labels(status=overall_status.value).inc()
        evaluation_score_histogram.observe(overall_score)

        logger.info(
            "evaluation_completed",
            session_id=str(turn.session_id),
            overall_score=overall_score,
            status=overall_status.value,
        )
        return run

    async def get_run(self, run_id: UUID) -> EvaluationRun:
        return await self._repo.get_run(run_id)

    async def list_for_session(
        self,
        session_id: UUID,
        *,
        org_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EvaluationRun]:
        return await self._repo.list_for_session(
            session_id, org_id=org_id, limit=limit, offset=offset
        )


def _overall_status(metrics: list[EvaluationMetric]) -> EvaluationStatus:
    if any(m.status == EvaluationStatus.FAILED for m in metrics):
        return EvaluationStatus.FAILED
    if any(m.status == EvaluationStatus.WARNING for m in metrics):
        return EvaluationStatus.WARNING
    return EvaluationStatus.PASSED
