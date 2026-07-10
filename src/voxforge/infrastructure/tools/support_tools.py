"""Customer support builtin tools backed by provider ports."""

from __future__ import annotations

import json
from typing import Any

from voxforge.core.domain.support import TicketCreateRequest
from voxforge.core.interfaces.support import KnowledgeBaseProvider, TicketingProvider
from voxforge.infrastructure.observability.telemetry import get_tracer

_tracer = get_tracer(__name__)


def _format_kb_result(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, default=str)


def _format_ticket(ticket: dict[str, Any]) -> str:
    return json.dumps(ticket, indent=2, default=str)


class KnowledgeBaseLookupTool:
    name = "knowledge_base_lookup"
    required_scopes = ["knowledge:read"]
    description = (
        "Search the customer knowledge base for articles relevant to the caller's question. "
        "Use before creating tickets when self-service answers may exist."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query from the customer",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum articles to return (default 3)",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, knowledge_base: KnowledgeBaseProvider) -> None:
        self._knowledge_base = knowledge_base

    async def invoke(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ValueError("query is required")

        limit = int(arguments.get("limit", 3))
        with _tracer.start_as_current_span("support.knowledge_base_lookup") as span:
            span.set_attribute("voxforge.support.query", query)
            result = await self._knowledge_base.search(query, limit=limit)
            span.set_attribute("voxforge.support.result_count", result.total)
            payload = {
                "query": result.query,
                "total": result.total,
                "articles": [article.model_dump(mode="json") for article in result.articles],
            }
            return _format_kb_result(payload)


class TicketLookupTool:
    name = "ticket_lookup"
    required_scopes = ["sessions:read"]
    description = (
        "Look up an existing support ticket by ticket ID or customer email. "
        "Use when the caller references a prior case or asks about ticket status."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "description": "Ticket ID e.g. TKT-1001",
            },
            "customer_email": {
                "type": "string",
                "description": "Customer email to list recent tickets",
            },
        },
    }

    def __init__(self, ticketing: TicketingProvider) -> None:
        self._ticketing = ticketing

    async def invoke(self, arguments: dict[str, Any]) -> str:
        ticket_id = str(arguments.get("ticket_id", "")).strip()
        customer_email = str(arguments.get("customer_email", "")).strip()

        if not ticket_id and not customer_email:
            raise ValueError("ticket_id or customer_email is required")

        with _tracer.start_as_current_span("support.ticket_lookup") as span:
            if ticket_id:
                span.set_attribute("voxforge.support.ticket_id", ticket_id)
                ticket = await self._ticketing.lookup_ticket(ticket_id)
                if ticket is None:
                    return json.dumps({"found": False, "ticket_id": ticket_id})
                return _format_ticket({"found": True, "ticket": ticket.model_dump(mode="json")})

            span.set_attribute("voxforge.support.customer_email", customer_email)
            tickets = await self._ticketing.lookup_by_customer_email(customer_email)
            span.set_attribute("voxforge.support.result_count", len(tickets))
            return _format_kb_result(
                {
                    "customer_email": customer_email,
                    "total": len(tickets),
                    "tickets": [ticket.model_dump(mode="json") for ticket in tickets],
                }
            )


class TicketCreateTool:
    name = "ticket_create"
    required_scopes = ["handoffs:write"]
    description = (
        "Create a new support ticket when the issue cannot be resolved via the knowledge base "
        "or requires human follow-up. Include a clear subject and description."
    )
    parameters = {
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Short summary of the customer's issue",
            },
            "description": {
                "type": "string",
                "description": "Detailed description including relevant context",
            },
            "customer_email": {
                "type": "string",
                "description": "Customer email for follow-up",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "normal", "high", "urgent"],
                "description": "Ticket priority (default normal)",
            },
            "session_id": {
                "type": "string",
                "description": "Voice session ID for idempotent ticket creation",
            },
        },
        "required": ["subject", "description"],
    }

    def __init__(self, ticketing: TicketingProvider) -> None:
        self._ticketing = ticketing

    async def invoke(self, arguments: dict[str, Any]) -> str:
        subject = str(arguments.get("subject", "")).strip()
        description = str(arguments.get("description", "")).strip()
        if not subject or not description:
            raise ValueError("subject and description are required")

        request = TicketCreateRequest(
            subject=subject,
            description=description,
            customer_email=str(arguments.get("customer_email", "")).strip() or None,
            priority=str(arguments.get("priority", "normal")),
            session_id=str(arguments.get("session_id", "")).strip() or None,
        )

        with _tracer.start_as_current_span("support.ticket_create") as span:
            span.set_attribute("voxforge.support.priority", request.priority)
            ticket = await self._ticketing.create_ticket(request)
            span.set_attribute("voxforge.support.ticket_id", ticket.id)
            return _format_ticket({"created": True, "ticket": ticket.model_dump(mode="json")})


def build_support_tools(
    knowledge_base: KnowledgeBaseProvider,
    ticketing: TicketingProvider,
) -> list[Any]:
    return [
        KnowledgeBaseLookupTool(knowledge_base),
        TicketLookupTool(ticketing),
        TicketCreateTool(ticketing),
    ]
