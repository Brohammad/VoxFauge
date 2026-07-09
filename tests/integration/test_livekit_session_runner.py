"""Integration tests for LiveKit session runner (no LiveKit server required)."""

import asyncio
import struct
from dataclasses import dataclass
from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.entities import SessionPhase, TransportType
from voxforge.core.domain.events import AudioChunk
from voxforge.infrastructure.livekit.audio_publisher import NullAudioPublisher
from voxforge.modules.livekit_gateway.application.session_runner import LiveKitSessionRunner


@dataclass
class FakeFrame:
    data: bytes
    sample_rate: int = 16_000
    num_channels: int = 1


class FakeResponseGenerator:
    def __init__(self) -> None:
        self._sessions: dict = {}

    def init_session(self, session_id) -> None:
        self._sessions[session_id] = []

    def set_session_org(self, session_id, org_id) -> None:
        pass

    def load_history(self, session_id, messages) -> None:
        pass

    def clear_session(self, session_id) -> None:
        self._sessions.pop(session_id, None)


class FakePipeline:
    def __init__(self) -> None:
        self.interrupts = 0
        self.turns = 0

    def set_session_org(self, session_id, org_id) -> None:
        pass

    async def run_listening(self, session_id, audio_queue, callbacks, *, language=None) -> None:
        self.turns += 1
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
        await callbacks.on_audio(AudioChunk(data=b"\x00\x00", sample_rate=16_000))

    async def interrupt(self, session_id) -> None:
        self.interrupts += 1


class FakeSessionManager:
    def __init__(self) -> None:
        self.phase = SessionPhase.LISTENING
        self.activated = False
        self.ended = False

    async def get_session(self, session_id, *, org_id=None):
        from datetime import UTC, datetime

        from voxforge.core.domain.entities import SessionStatus, VoiceSession

        return VoiceSession(
            id=session_id,
            transport_type=TransportType.WEBRTC,
            status=SessionStatus.CREATED,
            org_id=org_id,
            started_at=datetime.now(UTC),
        )

    async def activate_session(self, session_id):
        self.activated = True
        return await self.get_session(session_id)

    async def resume_session(self, session_id, last_sequence=0):
        return await self.get_session(session_id)

    async def get_messages(self, session_id, offset=0, limit=50):
        return []

    async def get_session_config(self, session_id):
        return {}

    async def get_session_phase(self, session_id):
        return self.phase

    async def record_heartbeat(self, session_id) -> None:
        return None

    async def end_session(self, session_id, *, reason="normal"):
        self.ended = True
        return await self.get_session(session_id)

    async def commit(self) -> None:
        return None


async def _fake_audio_stream(frames: list[FakeFrame]):
    for frame in frames:
        yield frame
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_livekit_session_runner_ingress_and_turn():
    session_id = uuid4()
    settings = Settings(memory_enabled=False, tools_enabled=False, evaluation_enabled=False)
    session_manager = FakeSessionManager()
    pipeline = FakePipeline()
    response_generator = FakeResponseGenerator()
    runner = LiveKitSessionRunner(
        session_id=session_id,
        session_manager=session_manager,
        pipeline=pipeline,
        response_generator=response_generator,
        settings=settings,
        audio_publisher=NullAudioPublisher(),
    )
    await runner.prepare()
    samples = struct.pack("<160h", *([500] * 160))
    frames = [FakeFrame(data=samples)]
    await runner.start(_fake_audio_stream(frames))
    await asyncio.sleep(0.05)
    await runner.shutdown()
    assert session_manager.activated
    assert session_manager.ended
    assert pipeline.turns >= 1


@pytest.mark.asyncio
async def test_livekit_session_runner_barge_in_on_speaking_phase():
    session_id = uuid4()
    settings = Settings(memory_enabled=False, tools_enabled=False, evaluation_enabled=False)
    session_manager = FakeSessionManager()
    session_manager.phase = SessionPhase.SPEAKING
    pipeline = FakePipeline()
    response_generator = FakeResponseGenerator()
    runner = LiveKitSessionRunner(
        session_id=session_id,
        session_manager=session_manager,
        pipeline=pipeline,
        response_generator=response_generator,
        settings=settings,
        audio_publisher=NullAudioPublisher(),
    )
    await runner.prepare()
    samples = struct.pack("<80h", *([200] * 80))
    await runner.start(_fake_audio_stream([FakeFrame(data=samples)]))
    await asyncio.sleep(0.05)
    await runner.shutdown()
    assert pipeline.interrupts >= 1
