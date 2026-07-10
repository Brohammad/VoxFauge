from uuid import UUID

import pytest

from voxforge.modules.outcomes.application.service import OutcomeExtractionService


class _RepoStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def upsert_session_outcome(self, **kwargs):
        self.calls.append(kwargs)
        return None, True


@pytest.mark.asyncio
async def test_record_outcome_uses_explicit_metadata_flags():
    repo = _RepoStub()
    service = OutcomeExtractionService(repo)

    await service.record_outcome(
        org_id=UUID("00000000-0000-0000-0000-000000000010"),
        session_id=UUID("00000000-0000-0000-0000-000000000011"),
        user_transcript="I need billing help",
        assistant_response="Transferring you to a human agent.",
        interrupted=False,
        resolution_time_seconds=42.0,
        user_metadata={"intent": "billing_contact_change"},
        assistant_metadata={"task_success": True, "escalation": False},
    )

    assert len(repo.calls) == 1
    assert repo.calls[0]["intent"] == "billing_contact_change"
    assert repo.calls[0]["task_success"] is True
    assert repo.calls[0]["escalation"] is False
    assert repo.calls[0]["resolution_time_seconds"] == 42.0


@pytest.mark.asyncio
async def test_record_outcome_derives_signals_without_metadata():
    repo = _RepoStub()
    service = OutcomeExtractionService(repo)

    await service.record_outcome(
        org_id=UUID("00000000-0000-0000-0000-000000000010"),
        session_id=UUID("00000000-0000-0000-0000-000000000011"),
        user_transcript="Can I reset my password?",
        assistant_response="I updated your account access and the issue is resolved.",
        interrupted=False,
        resolution_time_seconds=12.0,
    )

    assert repo.calls[0]["intent"] == "account_access"
    assert repo.calls[0]["task_success"] is True
    assert repo.calls[0]["escalation"] is False


@pytest.mark.asyncio
async def test_record_outcome_marks_interrupted_turn_as_escalated_and_unsuccessful():
    repo = _RepoStub()
    service = OutcomeExtractionService(repo)

    await service.record_outcome(
        org_id=UUID("00000000-0000-0000-0000-000000000010"),
        session_id=UUID("00000000-0000-0000-0000-000000000011"),
        user_transcript="I need a refund",
        assistant_response="Let me transfer you.",
        interrupted=True,
        resolution_time_seconds=-1.0,
    )

    assert repo.calls[0]["intent"] == "refund_request"
    assert repo.calls[0]["task_success"] is False
    assert repo.calls[0]["escalation"] is True
    assert repo.calls[0]["resolution_time_seconds"] == 0.0
