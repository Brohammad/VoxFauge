from typing import Protocol

from voxforge.core.domain.evaluation import EvaluationMetric, TurnEvaluationInput


class Evaluator(Protocol):
    name: str

    def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric: ...
