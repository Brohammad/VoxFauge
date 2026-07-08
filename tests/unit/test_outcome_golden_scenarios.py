"""Golden scenario pack for deterministic outcome KPI extraction."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from voxforge.modules.outcomes.application.service import OutcomeExtractionService

ORG_ID = UUID("00000000-0000-0000-0000-000000000010")


@dataclass(frozen=True)
class GoldenScenario:
    name: str
    user_transcript: str
    assistant_response: str
    interrupted: bool
    expected_intent: str
    expected_task_success: bool
    expected_escalation: bool
    user_metadata: dict | None = None
    assistant_metadata: dict | None = None
    resolution_time_seconds: float = 30.0


GOLDEN_SCENARIOS = [
    GoldenScenario(
        name="billing_resolved",
        user_transcript="I need to update my billing contact.",
        assistant_response="I can help with that. I updated the billing contact successfully.",
        interrupted=False,
        expected_intent="billing_support",
        expected_task_success=True,
        expected_escalation=False,
    ),
    GoldenScenario(
        name="refund_escalate",
        user_transcript="I want a refund for last month.",
        assistant_response="I will transfer you to a human agent for refund approval.",
        interrupted=False,
        expected_intent="refund_request",
        expected_task_success=False,
        expected_escalation=True,
    ),
    GoldenScenario(
        name="password_reset_success",
        user_transcript="I forgot my password and cannot login.",
        assistant_response="Done. I reset your password and the issue is fixed.",
        interrupted=False,
        expected_intent="account_access",
        expected_task_success=True,
        expected_escalation=False,
    ),
    GoldenScenario(
        name="subscription_cancel_handoff",
        user_transcript="Please cancel my subscription.",
        assistant_response="I am starting a handoff to a live agent for cancellation.",
        interrupted=False,
        expected_intent="subscription_change",
        expected_task_success=False,
        expected_escalation=True,
    ),
    GoldenScenario(
        name="general_unresolved",
        user_transcript="Can you explain how the product works?",
        assistant_response="I am not sure about that and don't have access to those docs.",
        interrupted=False,
        expected_intent="general_support",
        expected_task_success=False,
        expected_escalation=False,
    ),
    GoldenScenario(
        name="explicit_intent_override",
        user_transcript="Can you help me with this?",
        assistant_response="I can help with that. I completed the requested change.",
        interrupted=False,
        expected_intent="billing_contact_change",
        expected_task_success=True,
        expected_escalation=False,
        user_metadata={"intent": "Billing Contact Change"},
    ),
    GoldenScenario(
        name="interrupted_turn",
        user_transcript="I need billing help right now.",
        assistant_response="Sure, let me pull up your account.",
        interrupted=True,
        expected_intent="billing_support",
        expected_task_success=False,
        expected_escalation=True,
    ),
    GoldenScenario(
        name="explicit_escalation_false",
        user_transcript="Please escalate this to ops.",
        assistant_response="I transferred the case but kept working on a resolution.",
        interrupted=False,
        expected_intent="general_support",
        expected_task_success=True,
        expected_escalation=False,
        assistant_metadata={"escalation": False, "task_success": True},
    ),
    GoldenScenario(
        name="unable_to_resolve",
        user_transcript="I need help changing my login email.",
        assistant_response="I can't update that from here and failed to complete it.",
        interrupted=False,
        expected_intent="account_access",
        expected_task_success=False,
        expected_escalation=False,
    ),
    GoldenScenario(
        name="refund_resolved_without_handoff",
        user_transcript="Please process my refund request.",
        assistant_response="I processed the refund and the request is resolved.",
        interrupted=False,
        expected_intent="refund_request",
        expected_task_success=True,
        expected_escalation=False,
    ),
]


class _RepoStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def upsert_session_outcome(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", GOLDEN_SCENARIOS, ids=lambda s: s.name)
async def test_golden_outcome_extraction(scenario: GoldenScenario):
    repo = _RepoStub()
    service = OutcomeExtractionService(repo)

    await service.record_outcome(
        org_id=ORG_ID,
        session_id=uuid4(),
        user_transcript=scenario.user_transcript,
        assistant_response=scenario.assistant_response,
        interrupted=scenario.interrupted,
        resolution_time_seconds=scenario.resolution_time_seconds,
        user_metadata=scenario.user_metadata,
        assistant_metadata=scenario.assistant_metadata,
    )

    assert len(repo.calls) == 1
    result = repo.calls[0]
    assert result["intent"] == scenario.expected_intent
    assert result["task_success"] is scenario.expected_task_success
    assert result["escalation"] is scenario.expected_escalation


@pytest.mark.asyncio
async def test_golden_pack_accuracy_gate():
    """Fail the pack if KPI extraction accuracy drops under 90%."""
    repo = _RepoStub()
    service = OutcomeExtractionService(repo)
    passed = 0

    for scenario in GOLDEN_SCENARIOS:
        await service.record_outcome(
            org_id=ORG_ID,
            session_id=uuid4(),
            user_transcript=scenario.user_transcript,
            assistant_response=scenario.assistant_response,
            interrupted=scenario.interrupted,
            resolution_time_seconds=scenario.resolution_time_seconds,
            user_metadata=scenario.user_metadata,
            assistant_metadata=scenario.assistant_metadata,
        )
        result = repo.calls[-1]
        if (
            result["intent"] == scenario.expected_intent
            and result["task_success"] is scenario.expected_task_success
            and result["escalation"] is scenario.expected_escalation
        ):
            passed += 1

    accuracy = passed / len(GOLDEN_SCENARIOS)
    assert accuracy >= 0.9
    assert passed == len(GOLDEN_SCENARIOS)
