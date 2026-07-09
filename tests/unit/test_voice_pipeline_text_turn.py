from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from voxforge.core.domain.entities import TurnMetrics
from voxforge.modules.voice_gateway.application.pipeline import VoicePipelineService


@pytest.mark.asyncio
async def test_run_text_turn_skips_stt_and_returns_metrics():
    session_id = uuid4()
    expected = TurnMetrics(stt_ms=0.0, llm_first_token_ms=10.0, e2e_ms=50.0)

    pipeline = VoicePipelineService(
        session_manager=MagicMock(),
        stt_provider=MagicMock(),
        response_generator=MagicMock(),
        tts_provider=MagicMock(),
        settings=MagicMock(),
    )
    pipeline._process_turn = AsyncMock(return_value=expected)  # noqa: SLF001

    metrics = await pipeline.run_text_turn(
        session_id,
        "Hello there",
        user_metadata={"intent": "greeting"},
    )

    pipeline._process_turn.assert_awaited_once()  # noqa: SLF001
    call_kwargs = pipeline._process_turn.await_args.kwargs  # noqa: SLF001
    assert call_kwargs["stt_ms"] == 0.0
    assert call_kwargs["user_metadata_extra"] == {"intent": "greeting"}
    assert metrics.e2e_ms == 50.0
