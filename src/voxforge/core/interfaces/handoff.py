"""Ports for human handoff orchestration and assignment."""

from typing import Protocol
from uuid import UUID

from voxforge.core.domain.handoff import (
    AssignmentStrategy,
    ConversationSnapshot,
    EscalationPolicy,
    HandoffAssignment,
    HandoffPackage,
    HandoffRecord,
    HandoffTrigger,
    TurnHandoffContext,
)
from voxforge.core.domain.handoff import HandoffDecision as HandoffDecisionModel


class HandoffPolicyEvaluator(Protocol):
    """Evaluate whether a turn should trigger handoff."""

    def evaluate(
        self,
        context: TurnHandoffContext,
        policy: EscalationPolicy,
    ) -> HandoffDecisionModel: ...


class HandoffStore(Protocol):
    """Persistence for handoff records and events."""

    async def create_handoff(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        trigger: HandoffTrigger,
        trigger_reason: str,
        confidence_score: float | None = None,
        metadata: dict | None = None,
    ) -> HandoffRecord: ...

    async def get_by_session(
        self,
        session_id: UUID,
        *,
        org_id: UUID,
    ) -> HandoffRecord | None: ...

    async def get_handoff(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
    ) -> HandoffRecord | None: ...

    async def update_status(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
        status: str,
        **fields: object,
    ) -> HandoffRecord: ...

    async def record_event(
        self,
        handoff_id: UUID,
        *,
        org_id: UUID,
        event_type: str,
        payload: dict | None = None,
    ) -> None: ...

    async def save_snapshot(
        self,
        *,
        handoff_id: UUID,
        session_id: UUID,
        org_id: UUID,
        message_count: int,
        snapshot: dict,
    ) -> ConversationSnapshot: ...


class AssignmentProvider(Protocol):
    """Assign a human agent to a handoff."""

    async def assign(
        self,
        *,
        org_id: UUID,
        handoff_id: UUID,
        strategy: AssignmentStrategy,
        intent: str | None = None,
    ) -> HandoffAssignment: ...


class ConversationSummarizerPort(Protocol):
    """Generate a conversation summary for human context."""

    async def summarize(
        self,
        *,
        session_id: UUID,
        org_id: UUID,
        max_messages: int = 50,
    ) -> str: ...


class ReplayLinkGenerator(Protocol):
    """Generate signed replay URLs for handoff packages."""

    def generate(
        self,
        *,
        session_id: UUID,
        org_id: UUID,
        handoff_id: UUID,
    ) -> str: ...


class HandoffOrchestratorPort(Protocol):
    """Orchestrate the full handoff flow."""

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
    ) -> HandoffPackage: ...

    async def accept_handoff(
        self,
        *,
        handoff_id: UUID,
        org_id: UUID,
        user_id: UUID,
    ) -> HandoffRecord: ...

    async def complete_handoff(
        self,
        *,
        handoff_id: UUID,
        org_id: UUID,
        resolution: str = "resolved",
    ) -> HandoffRecord: ...
