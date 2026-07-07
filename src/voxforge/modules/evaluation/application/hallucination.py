"""LLM-as-judge hallucination detection evaluator."""

import json
import re

from voxforge.config import Settings
from voxforge.core.domain.evaluation import (
    EvaluationMetric,
    EvaluationStatus,
    MetricName,
    TurnEvaluationInput,
)
from voxforge.core.interfaces.providers import LLMProvider
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.modules.evaluation.application.evaluators import _status_from_score

logger = get_logger(__name__)

_JUDGE_PROMPT = """You are an evaluation judge for a voice AI assistant.
Score whether the assistant response is grounded and free of hallucinations.

User question:
{user_transcript}

Assistant response:
{assistant_response}

Retrieved context (may be empty):
{context}

Reply with JSON only:
{{"score": 0.0-1.0, "hallucinated": true/false, "reason": "brief explanation"}}
"""


class HallucinationEvaluator:
    name = MetricName.HALLUCINATION.value

    def __init__(self, settings: Settings, llm: LLMProvider) -> None:
        self._settings = settings
        self._llm = llm
        self._model = settings.evaluation_judge_model

    async def evaluate(self, turn: TurnEvaluationInput) -> EvaluationMetric:
        if not turn.assistant_response.strip():
            return EvaluationMetric(
                name=MetricName.HALLUCINATION,
                score=0.0,
                status=EvaluationStatus.FAILED,
                details={"reason": "empty response"},
            )

        context = "\n".join(turn.context_snippets) if turn.context_snippets else "(none)"
        prompt = _JUDGE_PROMPT.format(
            user_transcript=turn.user_transcript,
            assistant_response=turn.assistant_response,
            context=context,
        )

        from voxforge.core.domain.entities import MessageRole
        from voxforge.modules.memory.application.context_builder import ChatMessageLike

        messages = [ChatMessageLike(role=MessageRole.USER, content=prompt)]
        text_parts: list[str] = []
        try:
            async for event in self._llm.generate_stream(messages, model=self._model):
                if event.text:
                    text_parts.append(event.text)
        except Exception as exc:
            logger.warning("hallucination_judge_failed", error=str(exc))
            return EvaluationMetric(
                name=MetricName.HALLUCINATION,
                score=0.5,
                status=EvaluationStatus.WARNING,
                details={"reason": "judge unavailable", "error": str(exc)},
            )

        parsed = _parse_judge_response("".join(text_parts))
        score = float(parsed.get("score", 0.5))
        score = max(0.0, min(1.0, score))

        return EvaluationMetric(
            name=MetricName.HALLUCINATION,
            score=round(score, 3),
            status=_status_from_score(score),
            details={
                "hallucinated": parsed.get("hallucinated"),
                "reason": parsed.get("reason"),
            },
        )


def _parse_judge_response(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"score": 0.5, "hallucinated": None, "reason": "unparseable judge output"}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {"score": 0.5, "hallucinated": None, "reason": "invalid judge JSON"}
