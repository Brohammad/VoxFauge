#!/usr/bin/env python3
"""CI evaluation quality gate — fails if synthetic scenarios score below threshold."""

from __future__ import annotations

import os
import sys
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


SCENARIOS: list[dict] = [
    {
        "name": "fast_complete_turn",
        "turn": {
            "user_transcript": "What is the capital of France?",
            "assistant_response": "The capital of France is Paris.",
            "e2e_ms": 1200.0,
        },
        "min_score": 0.85,
    },
    {
        "name": "tool_success_turn",
        "turn": {
            "user_transcript": "What time is it?",
            "assistant_response": "It is 3 PM.",
            "e2e_ms": 1800.0,
            "tool_calls": [{"status": "success"}],
        },
        "min_score": 0.8,
    },
    {
        "name": "interrupted_turn",
        "turn": {
            "user_transcript": "Tell me a long story",
            "assistant_response": "Once upon a",
            "e2e_ms": 900.0,
            "interrupted": True,
        },
        "min_score": 0.4,
        "max_score": 0.95,
    },
]


def run_gate() -> int:
    settings = Settings(
        evaluation_enabled=True,
        evaluation_e2e_target_ms=float(os.getenv("EVAL_GATE_E2E_TARGET_MS", "2000")),
    )
    min_overall = float(os.getenv("EVAL_GATE_MIN_OVERALL", "0.75"))

    evaluators = [
        LatencyEvaluator(settings),
        TaskCompletionEvaluator(),
        ToolAccuracyEvaluator(),
        ConversationQualityEvaluator(),
        CostEvaluator(settings),
    ]

    failures: list[str] = []
    scores: list[float] = []

    for scenario in SCENARIOS:
        turn = TurnEvaluationInput(session_id=uuid4(), **scenario["turn"])
        metrics = [e.evaluate(turn) for e in evaluators]
        overall = round(sum(m.score for m in metrics) / len(metrics), 3)
        scores.append(overall)

        min_score = scenario.get("min_score", 0.0)
        max_score = scenario.get("max_score", 1.0)
        if overall < min_score or overall > max_score:
            failures.append(
                f"{scenario['name']}: score {overall} outside [{min_score}, {max_score}]"
            )

        if any(m.status == EvaluationStatus.FAILED for m in metrics):
            failed = [m.name.value for m in metrics if m.status == EvaluationStatus.FAILED]
            if scenario["name"] != "interrupted_turn":
                failures.append(f"{scenario['name']}: failed metrics {failed}")

    avg = round(sum(scores) / len(scores), 3) if scores else 0.0
    print(f"Eval gate average score: {avg} (min required: {min_overall})")
    if avg < min_overall:
        failures.append(f"average score {avg} below gate {min_overall}")

    if failures:
        print("EVAL GATE FAILED:")
        for line in failures:
            print(f"  - {line}")
        return 1

    print("EVAL GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run_gate())
