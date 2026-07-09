from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from voxforge.core.domain.entities import TurnMetrics
from voxforge.infrastructure.voice.programmatic_runner import ProgrammaticPipelineRunner
from voxforge.modules.onboarding.application.sample_scripts import (
    BILLING_CONTACT_CHANGE,
    get_default_sample_script,
)


def test_get_default_sample_script():
    script = get_default_sample_script()
    assert script.script_id == BILLING_CONTACT_CHANGE.script_id
    assert "billing contact" in script.user_transcript.lower()


@pytest.mark.asyncio
async def test_programmatic_runner_delegates_to_pipeline():
    session_id = uuid4()
    org_id = uuid4()
    expected_metrics = TurnMetrics(stt_ms=0.0, e2e_ms=42.0)

    pipeline = MagicMock()
    pipeline.run_text_turn = AsyncMock(return_value=expected_metrics)
    pipeline.set_session_org = MagicMock()

    runner = ProgrammaticPipelineRunner(pipeline)
    metrics = await runner.run_scripted_turn(
        session_id,
        org_id,
        transcript=BILLING_CONTACT_CHANGE.user_transcript,
        user_metadata=BILLING_CONTACT_CHANGE.user_metadata,
    )

    pipeline.set_session_org.assert_called_once_with(session_id, org_id)
    pipeline.run_text_turn.assert_awaited_once_with(
        session_id,
        BILLING_CONTACT_CHANGE.user_transcript,
        user_metadata=BILLING_CONTACT_CHANGE.user_metadata,
    )
    assert metrics.e2e_ms == 42.0
