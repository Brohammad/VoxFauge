"""Tests for LLM-as-judge hallucination evaluator."""

import json
from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.evaluation import EvaluationStatus, TurnEvaluationInput
from voxforge.core.domain.events import TokenEvent
from voxforge.modules.evaluation.application.hallucination import (
    HallucinationEvaluator,
    _parse_judge_response,
)


class StubLLM:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def generate_stream(self, messages, *, model: str):
        yield TokenEvent(text=json.dumps(self._payload), is_final=False)
        yield TokenEvent(text="", is_final=True)


def _turn(**kwargs) -> TurnEvaluationInput:
    defaults = {
        "session_id": uuid4(),
        "user_transcript": "What is the capital of France?",
        "assistant_response": "Paris is the capital of France.",
        "context_snippets": ["France is a country in Europe."],
    }
    defaults.update(kwargs)
    return TurnEvaluationInput(**defaults)


def test_parse_judge_response_extracts_json():
    parsed = _parse_judge_response('Here is the result: {"score": 0.9, "hallucinated": false}')
    assert parsed["score"] == 0.9


@pytest.mark.asyncio
async def test_hallucination_evaluator_high_score():
    llm = StubLLM({"score": 0.95, "hallucinated": False, "reason": "grounded"})
    ev = HallucinationEvaluator(Settings(), llm)
    metric = await ev.evaluate(_turn())
    assert metric.status == EvaluationStatus.PASSED
    assert metric.score >= 0.9


@pytest.mark.asyncio
async def test_hallucination_evaluator_empty_response_fails():
    ev = HallucinationEvaluator(Settings(), StubLLM({}))
    metric = await ev.evaluate(_turn(assistant_response=""))
    assert metric.status == EvaluationStatus.FAILED
