"""Integration tests for evaluation persistence."""

from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.evaluation import TurnEvaluationInput
from voxforge.infrastructure.db.evaluation_repository import EvaluationRepository
from voxforge.modules.evaluation.application.service import EvaluationEngine


@pytest.mark.asyncio
async def test_evaluation_engine_persists_run(db_session):
    org_id = uuid4()
    session_id = uuid4()

    from voxforge.infrastructure.db.models import OrganizationModel, VoiceSessionModel

    db_session.add(OrganizationModel(id=org_id, name="Test Org", slug=f"org-{org_id.hex[:8]}"))
    db_session.add(
        VoiceSessionModel(id=session_id, org_id=org_id, status="active", transport_type="websocket")
    )
    await db_session.flush()

    engine = EvaluationEngine(EvaluationRepository(db_session), Settings(evaluation_enabled=True))
    run = await engine.evaluate_turn(
        TurnEvaluationInput(
            session_id=session_id,
            org_id=org_id,
            user_transcript="Hello",
            assistant_response="Hi there!",
            e2e_ms=1200.0,
            stt_ms=200.0,
            llm_first_token_ms=400.0,
            tts_first_byte_ms=600.0,
        )
    )

    assert run is not None
    assert run.overall_score > 0
    assert len(run.metrics) == 5

    runs = await engine.list_for_session(session_id, org_id=org_id)
    assert len(runs) == 1
