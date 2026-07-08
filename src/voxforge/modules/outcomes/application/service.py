from typing import Protocol
from uuid import UUID


class OutcomeStore(Protocol):
    async def upsert_session_outcome(
        self,
        *,
        org_id: UUID,
        session_id: UUID,
        intent: str,
        task_success: bool,
        escalation: bool,
        resolution_time_seconds: float,
    ): ...


class OutcomeExtractionService:
    def __init__(self, repository: OutcomeStore) -> None:
        self._repository = repository

    async def record_outcome(
        self,
        *,
        org_id: UUID | None,
        session_id: UUID,
        user_transcript: str,
        assistant_response: str,
        interrupted: bool,
        resolution_time_seconds: float | None,
        user_metadata: dict | None = None,
        assistant_metadata: dict | None = None,
    ) -> None:
        if org_id is None:
            return

        intent = self._derive_intent(user_transcript, user_metadata or {})
        escalation = self._derive_escalation(
            assistant_response, interrupted, assistant_metadata or {}
        )
        task_success = self._derive_task_success(
            assistant_response,
            interrupted,
            escalation,
            assistant_metadata or {},
        )
        effective_resolution_seconds = max(resolution_time_seconds or 0.0, 0.0)

        await self._repository.upsert_session_outcome(
            org_id=org_id,
            session_id=session_id,
            intent=intent,
            task_success=task_success,
            escalation=escalation,
            resolution_time_seconds=effective_resolution_seconds,
        )

    @staticmethod
    def _derive_intent(user_transcript: str, user_metadata: dict) -> str:
        explicit_intent = user_metadata.get("intent")
        if isinstance(explicit_intent, str) and explicit_intent.strip():
            return explicit_intent.strip().lower().replace(" ", "_")

        text = user_transcript.lower()
        if "billing" in text:
            return "billing_support"
        if "refund" in text:
            return "refund_request"
        if "password" in text or "login" in text:
            return "account_access"
        if "cancel" in text or "subscription" in text:
            return "subscription_change"
        return "general_support"

    @staticmethod
    def _derive_escalation(
        assistant_response: str, interrupted: bool, assistant_metadata: dict
    ) -> bool:
        explicit_flag = assistant_metadata.get("escalation")
        if isinstance(explicit_flag, bool):
            return explicit_flag
        escalated_flag = assistant_metadata.get("escalated")
        if isinstance(escalated_flag, bool):
            return escalated_flag

        text = assistant_response.lower()
        handoff_phrases = (
            "human agent",
            "live agent",
            "escalat",
            "transfer",
            "handoff",
        )
        return interrupted or any(phrase in text for phrase in handoff_phrases)

    @staticmethod
    def _derive_task_success(
        assistant_response: str,
        interrupted: bool,
        escalation: bool,
        assistant_metadata: dict,
    ) -> bool:
        explicit_flag = assistant_metadata.get("task_success")
        if isinstance(explicit_flag, bool):
            return explicit_flag

        if interrupted or escalation:
            return False

        text = assistant_response.lower()
        success_phrases = (
            "resolved",
            "completed",
            "updated",
            "done",
            "fixed",
            "i can help with that",
        )
        uncertainty_phrases = (
            "cannot",
            "can't",
            "unable",
            "not sure",
            "don't have access",
            "failed",
        )
        has_success_signal = any(phrase in text for phrase in success_phrases)
        has_uncertainty_signal = any(phrase in text for phrase in uncertainty_phrases)
        return has_success_signal and not has_uncertainty_signal
