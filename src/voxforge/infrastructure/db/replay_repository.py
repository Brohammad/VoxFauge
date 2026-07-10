from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from voxforge.core.domain.replay import (
    ExplainabilityItem,
    SessionOutcomeSummary,
    SessionReplay,
    SessionReplayEvent,
)
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.infrastructure.db.models import (
    EvaluationRunModel,
    HandoffEventModel,
    MessageModel,
    OutcomeKPIModel,
    SessionMetricModel,
    ToolCallModel,
    VoiceSessionModel,
)


class ReplayRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_session_replay(
        self, session_id: UUID, *, org_id: UUID | None = None
    ) -> SessionReplay:
        session_model = await self._session.get(VoiceSessionModel, session_id)
        if session_model is None:
            raise SessionNotFoundError(str(session_id))
        if org_id is not None and session_model.org_id != org_id:
            raise SessionNotFoundError(str(session_id))

        messages = (
            await self._session.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.asc())
            )
        ).scalars().all()

        tool_calls = (
            await self._session.execute(
                select(ToolCallModel)
                .where(ToolCallModel.session_id == session_id)
                .order_by(ToolCallModel.created_at.asc())
            )
        ).scalars().all()

        evaluations = (
            await self._session.execute(
                select(EvaluationRunModel)
                .where(EvaluationRunModel.session_id == session_id)
                .options(selectinload(EvaluationRunModel.metrics))
                .order_by(EvaluationRunModel.created_at.asc())
            )
        ).scalars().all()

        metrics = (
            await self._session.execute(
                select(SessionMetricModel)
                .where(SessionMetricModel.session_id == session_id)
                .order_by(SessionMetricModel.recorded_at.asc())
            )
        ).scalars().all()

        outcome_model = (
            await self._session.execute(
                select(OutcomeKPIModel).where(OutcomeKPIModel.session_id == session_id).limit(1)
            )
        ).scalar_one_or_none()

        handoff_event_rows: list[HandoffEventModel] = []
        if getattr(session_model, "handoff_id", None) is not None:
            handoff_event_rows = (
                await self._session.execute(
                    select(HandoffEventModel)
                    .where(HandoffEventModel.handoff_id == session_model.handoff_id)
                    .order_by(HandoffEventModel.created_at.asc())
                )
            ).scalars().all()

        events: list[SessionReplayEvent] = []

        for message in messages:
            events.append(
                SessionReplayEvent(
                    event_type="message",
                    timestamp=message.created_at,
                    summary=message.content[:160],
                    status=None,
                    role=message.role,
                    payload={
                        "message_id": str(message.id),
                        "content_type": message.content_type,
                        "provider_metadata": message.provider_metadata or {},
                    },
                )
            )

        for call in tool_calls:
            events.append(
                SessionReplayEvent(
                    event_type="tool_call",
                    timestamp=call.created_at,
                    summary=f"{call.tool_name}: {call.status}",
                    status=call.status,
                    payload={
                        "tool_call_id": str(call.id),
                        "tool_name": call.tool_name,
                        "arguments": call.arguments or {},
                        "result": call.result,
                        "latency_ms": call.latency_ms,
                        "error": call.error,
                    },
                )
            )

        for run in evaluations:
            events.append(
                SessionReplayEvent(
                    event_type="evaluation",
                    timestamp=run.created_at,
                    summary=f"Score {run.overall_score:.2f} — {run.overall_status}",
                    status=run.overall_status,
                    payload={
                        "evaluation_id": str(run.id),
                        "overall_score": run.overall_score,
                        "user_transcript": run.user_transcript,
                        "assistant_response": run.assistant_response,
                        "metrics": [
                            {
                                "name": metric.name,
                                "score": metric.score,
                                "value": metric.value,
                                "unit": metric.unit,
                                "status": metric.status,
                            }
                            for metric in run.metrics
                        ],
                    },
                )
            )

        for metric in metrics:
            events.append(
                SessionReplayEvent(
                    event_type="metric",
                    timestamp=metric.recorded_at,
                    summary=f"{metric.metric_name}={metric.value_ms:.1f}ms",
                    status=None,
                    payload={
                        "metric_name": metric.metric_name,
                        "value_ms": metric.value_ms,
                    },
                )
            )

        for handoff_event in handoff_event_rows:
            events.append(
                SessionReplayEvent(
                    event_type="handoff",
                    timestamp=handoff_event.created_at,
                    summary=f"handoff:{handoff_event.event_type}",
                    status=handoff_event.event_type,
                    payload=handoff_event.payload or {},
                )
            )

        outcome: SessionOutcomeSummary | None = None
        if outcome_model is not None:
            outcome = SessionOutcomeSummary(
                intent=outcome_model.intent,
                task_success=outcome_model.task_success,
                escalation=outcome_model.escalation,
                resolution_time_seconds=outcome_model.resolution_time_seconds,
                recorded_at=outcome_model.recorded_at,
            )
            events.append(
                SessionReplayEvent(
                    event_type="outcome",
                    timestamp=outcome_model.recorded_at,
                    summary=(
                        f"intent={outcome_model.intent} "
                        f"success={outcome_model.task_success} "
                        f"escalation={outcome_model.escalation}"
                    ),
                    status="success" if outcome_model.task_success else "unsuccessful",
                    payload={
                        "intent": outcome_model.intent,
                        "task_success": outcome_model.task_success,
                        "escalation": outcome_model.escalation,
                        "resolution_time_seconds": outcome_model.resolution_time_seconds,
                    },
                )
            )

        events.sort(key=lambda event: event.timestamp)
        explanations = self._build_explanations(messages, outcome)

        return SessionReplay(
            session_id=session_model.id,
            status=session_model.status,
            started_at=session_model.started_at,
            ended_at=session_model.ended_at,
            transport_type=session_model.transport_type,
            metadata=session_model.metadata_ or {},
            outcome=outcome,
            explanations=explanations,
            events=events,
        )

    @staticmethod
    def _build_explanations(
        messages: list[MessageModel],
        outcome: SessionOutcomeSummary | None,
    ) -> list[ExplainabilityItem]:
        explanations: list[ExplainabilityItem] = []

        for message in messages:
            if message.role != "assistant":
                continue
            metadata = message.provider_metadata or {}
            trace = metadata.get("agent_trace")
            if not isinstance(trace, list):
                continue
            for step in trace:
                if not isinstance(step, dict):
                    continue
                agent = str(step.get("agent", ""))
                status = str(step.get("status", "completed"))
                summary = str(step.get("summary", "")).strip()
                if agent == "safety":
                    explanations.append(
                        ExplainabilityItem(
                            kind="safety",
                            decision="allowed" if status == "completed" else "blocked",
                            reason=summary or status,
                        )
                    )
                elif agent == "critic":
                    explanations.append(
                        ExplainabilityItem(
                            kind="critic",
                            decision="approved" if status == "completed" else "revise",
                            reason=summary or status,
                        )
                    )
                elif agent == "tool":
                    explanations.append(
                        ExplainabilityItem(
                            kind="tool",
                            decision=status,
                            reason=summary or "tool step",
                        )
                    )

        if outcome is not None:
            if outcome.task_success:
                decision = "resolved"
                reason = f"Intent `{outcome.intent}` completed without escalation."
            elif outcome.escalation:
                decision = "escalated"
                reason = f"Intent `{outcome.intent}` required handoff/escalation."
            else:
                decision = "unresolved"
                reason = f"Intent `{outcome.intent}` did not complete successfully."
            explanations.append(
                ExplainabilityItem(kind="outcome", decision=decision, reason=reason)
            )

        return explanations
