"""Integration tests for tool call persistence."""

from uuid import uuid4

import pytest

from voxforge.core.domain.tools import ToolCallStatus
from voxforge.infrastructure.db.tool_repository import ToolCallRepository


@pytest.mark.asyncio
async def test_tool_call_repository(db_session):
    org_id = uuid4()
    session_id = uuid4()

    from voxforge.infrastructure.db.models import OrganizationModel, VoiceSessionModel

    db_session.add(OrganizationModel(id=org_id, name="Test Org", slug=f"org-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(id=session_id, org_id=org_id, status="active", transport_type="websocket")
    )
    await db_session.flush()

    repo = ToolCallRepository(db_session)
    record = await repo.record_call(
        org_id=org_id,
        session_id=session_id,
        tool_name="calculate",
        arguments={"expression": "2+2"},
        result="4.0",
        status=ToolCallStatus.SUCCESS,
        latency_ms=12.5,
        error=None,
    )

    calls = await repo.list_for_session(session_id, org_id=org_id)
    assert len(calls) == 1
    assert calls[0].id == record.id
    assert calls[0].tool_name == "calculate"
