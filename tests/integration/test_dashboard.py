"""Integration tests for dashboard analytics."""

from uuid import uuid4

import pytest

from voxforge.infrastructure.db.dashboard_repository import DashboardRepository
from voxforge.modules.dashboard.application.service import DashboardService


@pytest.mark.asyncio
async def test_dashboard_overview(db_session):
    org_id = uuid4()
    session_id = uuid4()

    from voxforge.infrastructure.db.models import (
        EvaluationMetricModel,
        EvaluationRunModel,
        MessageModel,
        OrganizationModel,
        OutcomeKPIModel,
        SessionMetricModel,
        VoiceSessionModel,
    )

    db_session.add(OrganizationModel(id=org_id, name="Dash Org", slug=f"dash-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(
            id=session_id,
            org_id=org_id,
            status="completed",
            transport_type="websocket",
        )
    )
    db_session.add(
        MessageModel(session_id=session_id, role="user", content="Hi", content_type="text")
    )
    db_session.add(
        SessionMetricModel(session_id=session_id, metric_name="e2e_ms", value_ms=1500.0)
    )
    run_id = uuid4()
    db_session.add(
        EvaluationRunModel(
            id=run_id,
            org_id=org_id,
            session_id=session_id,
            user_transcript="Hi",
            assistant_response="Hello",
            overall_score=0.9,
            overall_status="passed",
        )
    )
    db_session.add(
        EvaluationMetricModel(
            run_id=run_id,
            name="cost",
            score=0.95,
            value=0.002,
            unit="usd",
            status="passed",
        )
    )
    db_session.add(
        OutcomeKPIModel(
            org_id=org_id,
            session_id=session_id,
            intent="billing_contact_change",
            task_success=True,
            escalation=False,
            resolution_time_seconds=95.0,
        )
    )
    await db_session.flush()

    service = DashboardService(DashboardRepository(db_session))
    overview = await service.get_overview(org_id)

    assert overview.total_sessions == 1
    assert overview.total_messages == 1
    assert overview.total_evaluations == 1
    assert overview.avg_e2e_latency_ms == 1500.0

    sessions = await service.get_recent_sessions(org_id)
    assert len(sessions) == 1
    assert sessions[0].message_count == 1

    latency = await service.get_latency_stats(org_id)
    assert any(b.metric_name == "e2e_ms" for b in latency)

    eval_summary = await service.get_evaluation_summary(org_id)
    assert eval_summary.total_runs == 1
    assert eval_summary.passed == 1

    outcomes = await service.get_outcome_summary(org_id)
    assert outcomes.total_sessions == 1
    assert outcomes.task_success_rate == 1.0
    assert outcomes.escalation_rate == 0.0
