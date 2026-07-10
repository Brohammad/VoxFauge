"""Handoff orchestration: ticket, summary, replay link, assignment, snapshot."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.handoff import (
    AssignmentStrategy,
    EscalationPolicy,
    HandoffAssignment,
    HandoffEventType,
    HandoffPackage,
    HandoffStatus,
    HandoffTrigger,
)
from voxforge.core.domain.support import TicketCreateRequest
from voxforge.core.interfaces.support import TicketingProvider
from voxforge.infrastructure.db.handoff_repository import HandoffRepository
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    handoff_duration_seconds,
    handoff_initiated_total,
    handoff_queue_depth,
)
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.infrastructure.providers.handoff.factory import create_assignment_provider
from voxforge.modules.handoff.application.replay_link import ReplayLinkService
from voxforge.modules.handoff.application.summarizer import ExtractiveConversationSummarizer
from voxforge.modules.session_manager.application.service import SessionManager

logger = get_logger(__name__)
_tracer = get_tracer(__name__)


class HandoffOrchestrator:
    def __init__(
        self,
        repository: HandoffRepository,
        ticketing: TicketingProvider,
        summarizer: ExtractiveConversationSummarizer,
        replay_links: ReplayLinkService,
        session_manager: SessionManager,
        settings: Settings,
    ) -> None:
        self._repo = repository
        self._ticketing = ticketing
        self._summarizer = summarizer
        self._replay_links = replay_links
        self._sessions = session_manager
        self._settings = settings
        self._assignment = create_assignment_provider(settings, repository)

    async def initiate_handoff(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        trigger: HandoffTrigger,
        reason: str,
        confidence_score: float | None = None,
        policy: EscalationPolicy,
        customer_email: str | None = None,
        priority: str = "normal",
    ) -> HandoffPackage:
        with _tracer.start_as_current_span("handoff.orchestrate") as span:
            span.set_attribute("voxforge.session_id", str(session_id))
            span.set_attribute("voxforge.handoff.trigger", trigger.value)

            existing = await self._repo.get_by_session(session_id, org_id=org_id)
            if existing is not None:
                return self._to_package(existing, policy)

            start = time.monotonic()
            record = await self._repo.create_handoff(
                org_id=org_id,
                session_id=session_id,
                trigger=trigger,
                trigger_reason=reason,
                confidence_score=confidence_score,
            )
            handoff_initiated_total.labels(trigger=trigger.value, org_id=str(org_id)).inc()

            ticket_id = None
            if policy.auto_create_ticket:
                ticket_start = time.monotonic()
                summary_preview = await self._summarizer.summarize(
                    session_id=session_id, org_id=org_id
                )
                replay_url, _ = self._replay_links.generate(
                    session_id=session_id, org_id=org_id, handoff_id=record.id
                )
                ticket = await self._ticketing.create_ticket(
                    TicketCreateRequest(
                        subject=f"Voice handoff — session {session_id}",
                        description=f"{reason}\n\nConversation preview:\n{summary_preview[:500]}",
                        customer_email=customer_email,
                        priority=priority,
                        session_id=str(session_id),
                        conversation_summary=summary_preview,
                        replay_url=replay_url,
                    )
                )
                ticket_id = ticket.id
                handoff_duration_seconds.labels(stage="ticket").observe(
                    time.monotonic() - ticket_start
                )
                await self._repo.record_event(
                    record.id,
                    org_id=org_id,
                    event_type=HandoffEventType.TICKET_CREATED.value,
                    payload={"ticket_id": ticket_id},
                )

            summary_start = time.monotonic()
            conversation_summary = await self._summarizer.summarize(
                session_id=session_id, org_id=org_id
            )
            handoff_duration_seconds.labels(stage="summary").observe(
                time.monotonic() - summary_start
            )
            await self._repo.record_event(
                record.id,
                org_id=org_id,
                event_type=HandoffEventType.SUMMARY_GENERATED.value,
                payload={"length": len(conversation_summary)},
            )

            replay_start = time.monotonic()
            replay_url, replay_token = self._replay_links.generate(
                session_id=session_id, org_id=org_id, handoff_id=record.id
            )
            handoff_duration_seconds.labels(stage="replay").observe(time.monotonic() - replay_start)
            await self._repo.record_event(
                record.id,
                org_id=org_id,
                event_type=HandoffEventType.REPLAY_LINKED.value,
                payload={"replay_url": replay_url},
            )

            assign_start = time.monotonic()
            assignment = await self._assignment.assign(
                org_id=org_id,
                handoff_id=record.id,
                strategy=policy.assignment_strategy,
            )
            handoff_duration_seconds.labels(stage="assign").observe(
                time.monotonic() - assign_start
            )
            await self._repo.record_event(
                record.id,
                org_id=org_id,
                event_type=HandoffEventType.ASSIGNED.value,
                payload={
                    "assignee_user_id": (
                        str(assignment.assignee_user_id) if assignment.assignee_user_id else None
                    ),
                    "assignee_email": assignment.assignee_email,
                },
            )

            messages = await self._sessions.get_messages(session_id, limit=100)
            snapshot_payload = {
                "messages": [
                    {
                        "id": str(m.id),
                        "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                        "content": m.content,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ]
            }
            await self._repo.save_snapshot(
                handoff_id=record.id,
                session_id=session_id,
                org_id=org_id,
                message_count=len(messages),
                snapshot=snapshot_payload,
            )

            now = datetime.now(UTC)
            status = (
                HandoffStatus.ASSIGNED.value
                if assignment.assignee_user_id or assignment.assignee_email
                else HandoffStatus.PENDING.value
            )
            record = await self._repo.update_status(
                record.id,
                org_id=org_id,
                status=status,
                ticket_id=ticket_id,
                ticket_provider=self._settings.ticketing_provider,
                conversation_summary=conversation_summary,
                replay_url=replay_url,
                replay_token=replay_token,
                assigned_to_user_id=assignment.assignee_user_id,
                assigned_to_email=assignment.assignee_email,
                assigned_at=now if assignment.assignee_user_id or assignment.assignee_email else None,
            )
            await self._repo.link_session(
                session_id=session_id,
                handoff_id=record.id,
                handoff_status=status,
            )
            await self._sessions.apply_handoff_pending(
                session_id,
                handoff_id=record.id,
                handoff_context={
                    "handoff_id": str(record.id),
                    "ticket_id": ticket_id,
                    "replay_url": replay_url,
                    "summary": conversation_summary,
                },
            )

            handoff_duration_seconds.labels(stage="total").observe(time.monotonic() - start)
            depth = await self._repo.count_pending(org_id=org_id)
            handoff_queue_depth.labels(org_id=str(org_id)).set(depth)

            logger.info(
                "handoff_initiated",
                handoff_id=str(record.id),
                session_id=str(session_id),
                trigger=trigger.value,
                ticket_id=ticket_id,
            )
            span.set_attribute("voxforge.handoff_id", str(record.id))
            return self._to_package(record, policy, assignment)

    async def accept_handoff(
        self,
        *,
        handoff_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ):
        record = await self._repo.get_handoff(handoff_id, org_id=org_id)
        if record is None:
            raise ValueError("Handoff not found")

        now = datetime.now(UTC)
        record = await self._repo.update_status(
            handoff_id,
            org_id=org_id,
            status=HandoffStatus.ACTIVE.value,
            assigned_to_user_id=user_id,
            accepted_at=now,
        )
        await self._repo.link_session(
            session_id=record.session_id,
            handoff_id=handoff_id,
            handoff_status=HandoffStatus.ACTIVE.value,
        )
        await self._repo.record_event(
            handoff_id,
            org_id=org_id,
            event_type=HandoffEventType.ACCEPTED.value,
            payload={"user_id": str(user_id)},
        )
        await self._sessions.apply_handoff_active(record.session_id, handoff_id=handoff_id)
        await self._sessions.resume_session(record.session_id)
        await self._repo.record_event(
            handoff_id,
            org_id=org_id,
            event_type=HandoffEventType.RESUMED.value,
            payload={"session_id": str(record.session_id)},
        )
        return record

    async def complete_handoff(
        self,
        *,
        handoff_id: UUID,
        org_id: UUID,
        resolution: str = "resolved",
    ):
        record = await self._repo.get_handoff(handoff_id, org_id=org_id)
        if record is None:
            raise ValueError("Handoff not found")

        now = datetime.now(UTC)
        record = await self._repo.update_status(
            handoff_id,
            org_id=org_id,
            status=HandoffStatus.COMPLETED.value,
            completed_at=now,
            metadata={**record.metadata, "resolution": resolution},
        )
        await self._repo.link_session(
            session_id=record.session_id,
            handoff_id=handoff_id,
            handoff_status=HandoffStatus.COMPLETED.value,
        )
        await self._repo.record_event(
            handoff_id,
            org_id=org_id,
            event_type=HandoffEventType.COMPLETED.value,
            payload={"resolution": resolution},
        )
        await self._sessions.clear_handoff(record.session_id)
        return record

    @staticmethod
    def _to_package(
        record,
        policy: EscalationPolicy,
        assignment: HandoffAssignment | None = None,
    ) -> HandoffPackage:
        if assignment is None and (
            record.assigned_to_user_id or record.assigned_to_email
        ):
            assignment = HandoffAssignment(
                handoff_id=record.id,
                assignee_user_id=record.assigned_to_user_id,
                assignee_email=record.assigned_to_email,
                strategy=AssignmentStrategy.ROUND_ROBIN,
            )
        return HandoffPackage(
            handoff_id=record.id,
            session_id=record.session_id,
            ticket_id=record.ticket_id,
            conversation_summary=record.conversation_summary or "",
            replay_url=record.replay_url or "",
            assignment=assignment,
            handoff_message=policy.handoff_message,
            trigger=record.trigger,
            confidence_score=record.confidence_score,
        )
