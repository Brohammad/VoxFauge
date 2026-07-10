"""Handoff tool for agent-initiated escalation."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from voxforge.core.domain.handoff import EscalationPolicy, HandoffTrigger
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.infrastructure.tools.tool_context import tool_org_id, tool_session_id
from voxforge.modules.handoff.application.orchestrator import HandoffOrchestrator

_tracer = get_tracer(__name__)


class HandoffToHumanTool:
    name = "handoff_to_human"
    description = (
        "Escalate the conversation to a human agent. Creates a support ticket, "
        "packages conversation context, and assigns a human operator."
    )
    parameters = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why the conversation is being escalated",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "Ticket priority (default normal)",
            },
            "customer_email": {
                "type": "string",
                "description": "Optional customer email for ticket follow-up",
            },
        },
        "required": ["reason"],
    }

    def __init__(self, orchestrator: HandoffOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def invoke(self, arguments: dict[str, Any]) -> str:
        org_id = tool_org_id.get()
        session_id = tool_session_id.get()
        if org_id is None or session_id is None:
            raise ValueError("handoff_to_human requires active session context")

        reason = str(arguments.get("reason", "")).strip()
        if not reason:
            raise ValueError("reason is required")

        priority = str(arguments.get("priority", "normal"))
        customer_email = str(arguments.get("customer_email", "")).strip() or None

        with _tracer.start_as_current_span("handoff.tool.invoke") as span:
            span.set_attribute("voxforge.session_id", str(session_id))
            package = await self._orchestrator.initiate_handoff(
                org_id=UUID(str(org_id)),
                session_id=UUID(str(session_id)),
                trigger=HandoffTrigger.AGENT_EXPLICIT,
                reason=reason,
                policy=EscalationPolicy(),
                customer_email=customer_email,
                priority=priority,
            )
            payload = {
                "handoff_id": str(package.handoff_id),
                "ticket_id": package.ticket_id,
                "replay_url": package.replay_url,
                "conversation_summary": package.conversation_summary,
                "handoff_message": package.handoff_message,
                "assignee_email": (
                    package.assignment.assignee_email if package.assignment else None
                ),
            }
            return json.dumps(payload, indent=2)
