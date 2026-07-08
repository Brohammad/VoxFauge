from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.infrastructure.db.dashboard_repository import DashboardRepository
from voxforge.infrastructure.db.models import (
    EvaluationRunModel,
    OrganizationModel,
    OutcomeKPIModel,
    SessionMetricModel,
    SupportTemplateModel,
    VoiceSessionModel,
)
from voxforge.modules.alerts.application.service import AlertService


@pytest.mark.asyncio
async def test_alert_service_flags_regressions(db_session):
    org_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)

    db_session.add(OrganizationModel(id=org_id, name="Alert Org", slug=f"alert-{org_id.hex[:8]}"))
    db_session.add(
        SupportTemplateModel(
            name="Customer Support Deflection",
            slug="customer-support-deflection",
            prompt_config={},
            tool_config={},
            eval_thresholds={
                "task_success_min": 0.9,
                "escalation_max": 0.2,
                "quality_min": 0.85,
                "e2e_latency_max_ms": 1000.0,
                "failed_evaluation_max_rate": 0.1,
            },
            is_default=True,
        )
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
        OutcomeKPIModel(
            org_id=org_id,
            session_id=session_id,
            intent="billing_support",
            task_success=False,
            escalation=True,
            resolution_time_seconds=40.0,
            recorded_at=now,
        )
    )
    db_session.add(
        EvaluationRunModel(
            org_id=org_id,
            session_id=session_id,
            user_transcript="help",
            assistant_response="cannot help",
            overall_score=0.4,
            overall_status="failed",
            created_at=now,
        )
    )
    db_session.add(
        SessionMetricModel(
            session_id=session_id,
            metric_name="e2e_ms",
            value_ms=2500.0,
            recorded_at=now,
        )
    )
    await db_session.flush()

    service = AlertService(db_session, DashboardRepository(db_session))
    summary = await service.get_alerts(org_id, days=7)

    codes = {alert.code for alert in summary.alerts}
    assert summary.active_count >= 3
    assert "task_success_regression" in codes
    assert "escalation_spike" in codes
    assert "quality_regression" in codes
    assert "latency_regression" in codes


@pytest.mark.asyncio
async def test_dashboard_alerts_endpoint(auth_client):
    register = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "alerts@example.com",
            "password": "securepass123",
            "full_name": "Alert User",
            "org_name": "Alert API Org",
        },
    )
    assert register.status_code == 201
    token = register.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await auth_client.get("/api/v1/dashboard/alerts?days=7", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "active_count" in payload
    assert "thresholds" in payload
    assert isinstance(payload["alerts"], list)
