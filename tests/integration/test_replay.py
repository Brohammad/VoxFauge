from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.infrastructure.db.models import (
    EvaluationMetricModel,
    EvaluationRunModel,
    MessageModel,
    OrganizationModel,
    OutcomeKPIModel,
    SessionMetricModel,
    ToolCallModel,
    VoiceSessionModel,
)
from voxforge.infrastructure.db.replay_repository import ReplayRepository
from voxforge.modules.replay.application.service import ReplayService


@pytest.mark.asyncio
async def test_session_replay_aggregates_timeline(db_session):
    org_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)

    db_session.add(OrganizationModel(id=org_id, name="Replay Org", slug=f"replay-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(
            id=session_id,
            org_id=org_id,
            status="completed",
            transport_type="websocket",
            started_at=now,
            ended_at=now,
        )
    )
    db_session.add(
        MessageModel(
            session_id=session_id,
            role="user",
            content="I need help with billing.",
            content_type="text",
            created_at=now,
        )
    )
    db_session.add(
        MessageModel(
            session_id=session_id,
            role="assistant",
            content="I updated your billing contact.",
            content_type="text",
            created_at=now,
        )
    )
    db_session.add(
        ToolCallModel(
            org_id=org_id,
            session_id=session_id,
            tool_name="ticket_lookup",
            arguments={"ticket_id": "T-1"},
            result="ok",
            status="success",
            latency_ms=12.0,
            created_at=now,
        )
    )
    run_id = uuid4()
    db_session.add(
        EvaluationRunModel(
            id=run_id,
            org_id=org_id,
            session_id=session_id,
            user_transcript="I need help with billing.",
            assistant_response="I updated your billing contact.",
            overall_score=0.91,
            overall_status="passed",
            created_at=now,
        )
    )
    db_session.add(
        EvaluationMetricModel(
            run_id=run_id,
            name="latency",
            score=0.95,
            value=1400.0,
            unit="ms",
            status="passed",
        )
    )
    db_session.add(
        SessionMetricModel(
            session_id=session_id,
            metric_name="e2e_ms",
            value_ms=1400.0,
            recorded_at=now,
        )
    )
    db_session.add(
        OutcomeKPIModel(
            org_id=org_id,
            session_id=session_id,
            intent="billing_support",
            task_success=True,
            escalation=False,
            resolution_time_seconds=42.0,
            recorded_at=now,
        )
    )
    await db_session.flush()

    service = ReplayService(ReplayRepository(db_session))
    replay = await service.get_session_replay(session_id, org_id=org_id)

    assert replay.session_id == session_id
    assert replay.status == "completed"
    assert replay.outcome is not None
    assert replay.outcome.intent == "billing_support"
    assert replay.outcome.task_success is True
    assert any(item.kind == "outcome" for item in replay.explanations)

    event_types = [event.event_type for event in replay.events]
    assert event_types.count("message") == 2
    assert "tool_call" in event_types
    assert "evaluation" in event_types
    assert "metric" in event_types
    assert "outcome" in event_types
    assert all(
        left.timestamp <= right.timestamp
        for left, right in zip(replay.events, replay.events[1:], strict=False)
    )


@pytest.mark.asyncio
async def test_session_replay_api_endpoint(auth_client):
    register = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "replay@example.com",
            "password": "securepass123",
            "full_name": "Replay User",
            "org_name": "Replay API Org",
        },
    )
    assert register.status_code == 201
    token = register.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    sample = await auth_client.post("/api/v1/onboarding/run-sample-call", headers=headers)
    assert sample.status_code == 200
    session_id = sample.json()["test_session_id"]

    response = await auth_client.get(f"/api/v1/sessions/{session_id}/replay", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["outcome"]["intent"] == "billing_contact_change"
    assert any(item["kind"] == "outcome" for item in payload["explanations"])
    assert any(event["event_type"] == "message" for event in payload["events"])
    assert any(event["event_type"] == "outcome" for event in payload["events"])


@pytest.mark.asyncio
async def test_session_replay_includes_agent_explainability(db_session):
    org_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)

    db_session.add(
        OrganizationModel(id=org_id, name="Explain Org", slug=f"explain-{org_id.hex[:8]}")
    )
    db_session.add(
        VoiceSessionModel(
            id=session_id,
            org_id=org_id,
            status="completed",
            transport_type="websocket",
            started_at=now,
            ended_at=now,
        )
    )
    db_session.add(
        MessageModel(
            session_id=session_id,
            role="assistant",
            content="I transferred you to a live agent.",
            content_type="text",
            provider_metadata={
                "agent_trace": [
                    {"agent": "safety", "status": "completed", "summary": "safe request"},
                    {"agent": "critic", "status": "revise", "summary": "needs clearer handoff"},
                    {"agent": "tool", "status": "success", "summary": "ticket_lookup"},
                ]
            },
            created_at=now,
        )
    )
    db_session.add(
        OutcomeKPIModel(
            org_id=org_id,
            session_id=session_id,
            intent="billing_support",
            task_success=False,
            escalation=True,
            resolution_time_seconds=18.0,
            recorded_at=now,
        )
    )
    await db_session.flush()

    service = ReplayService(ReplayRepository(db_session))
    replay = await service.get_session_replay(session_id, org_id=org_id)

    kinds = {item.kind: item for item in replay.explanations}
    assert kinds["safety"].decision == "allowed"
    assert kinds["critic"].decision == "revise"
    assert kinds["tool"].decision == "success"
    assert kinds["outcome"].decision == "escalated"
