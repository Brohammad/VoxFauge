import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.entities import SessionPhase, TurnMetrics
from voxforge.core.domain.events import AudioChunk, TranscriptEvent
from voxforge.core.interfaces.providers import SpeechProvider, TTSProvider
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    e2e_turn_latency_seconds,
    llm_first_token_seconds,
    stt_latency_seconds,
    tts_first_byte_seconds,
    turns_completed,
    turns_interrupted,
)
from voxforge.infrastructure.providers.tts.cartesia import token_stream_to_sentences
from voxforge.modules.conversation.application.engine import ConversationEngine
from voxforge.modules.session_manager.application.service import SessionManager

logger = get_logger(__name__)


@dataclass
class PipelineCallbacks:
    on_transcript: Callable[[TranscriptEvent], Any] = field(default=lambda e: None)
    on_token: Callable[[str], Any] = field(default=lambda t: None)
    on_audio: Callable[[AudioChunk], Any] = field(default=lambda c: None)
    on_metrics: Callable[[TurnMetrics], Any] = field(default=lambda m: None)
    on_error: Callable[[str, str], Any] = field(default=lambda c, m: None)


class VoicePipelineService:
    def __init__(
        self,
        session_manager: SessionManager,
        stt_provider: SpeechProvider,
        conversation_engine: ConversationEngine,
        tts_provider: TTSProvider,
        settings: Settings,
    ) -> None:
        self._sessions = session_manager
        self._stt = stt_provider
        self._conversation = conversation_engine
        self._tts = tts_provider
        self._settings = settings
        self._interrupt_event: asyncio.Event | None = None
        self._pipeline_task: asyncio.Task | None = None

    async def run_listening(
        self,
        session_id: UUID,
        audio_queue: asyncio.Queue[bytes | None],
        callbacks: PipelineCallbacks,
        *,
        language: str | None = None,
    ) -> None:
        """Listen for audio, transcribe, and process complete utterances."""

        async def audio_stream() -> AsyncIterator[bytes]:
            while True:
                chunk = await audio_queue.get()
                if chunk is None:
                    break
                yield chunk

        self._interrupt_event = asyncio.Event()
        turn_start = time.monotonic()
        first_partial_time: float | None = None
        final_transcript: str | None = None
        final_confidence: float | None = None

        try:
            async for event in self._stt.transcribe_stream(audio_stream(), language=language):
                if self._interrupt_event and self._interrupt_event.is_set():
                    break

                if event.is_partial:
                    if first_partial_time is None:
                        first_partial_time = time.monotonic()
                        stt_latency_seconds.observe(first_partial_time - turn_start)
                    await self._maybe_await(callbacks.on_transcript(event))
                else:
                    final_transcript = event.text
                    final_confidence = event.confidence
                    await self._maybe_await(callbacks.on_transcript(event))

            if final_transcript:
                await self._process_turn(
                    session_id,
                    final_transcript,
                    callbacks,
                    turn_start=turn_start,
                    stt_ms=(first_partial_time - turn_start) * 1000 if first_partial_time else None,
                    confidence=final_confidence,
                )
        except asyncio.CancelledError:
            logger.info("pipeline_listening_cancelled", session_id=str(session_id))
            raise
        except Exception as exc:
            logger.error("pipeline_listening_error", session_id=str(session_id), error=str(exc))
            await self._maybe_await(callbacks.on_error("pipeline_error", str(exc)))

    async def _process_turn(
        self,
        session_id: UUID,
        transcript: str,
        callbacks: PipelineCallbacks,
        *,
        turn_start: float,
        stt_ms: float | None,
        confidence: float | None,
    ) -> None:
        metrics = TurnMetrics(stt_ms=stt_ms)
        self._interrupt_event = asyncio.Event()

        await self._sessions.update_phase(session_id, SessionPhase.PROCESSING)
        await self._sessions.save_user_message(
            session_id, transcript, metadata={"confidence": confidence}
        )
        self._conversation.add_user_message(session_id, transcript)

        assistant_text = ""
        llm_start = time.monotonic()
        first_token_time: float | None = None
        first_audio_time: float | None = None

        async def token_iter() -> AsyncIterator[str]:
            nonlocal assistant_text, first_token_time
            async for event in self._conversation.generate_response(session_id):
                if self._interrupt_event and self._interrupt_event.is_set():
                    break
                if event.text:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                        metrics.llm_first_token_ms = (first_token_time - llm_start) * 1000
                        llm_first_token_seconds.observe(first_token_time - llm_start)
                    assistant_text += event.text
                    await self._maybe_await(callbacks.on_token(event.text))
                    yield event.text

        await self._sessions.update_phase(session_id, SessionPhase.SPEAKING)

        config = await self._sessions.get_session_config(session_id)
        voice_id = config.get("voice_id", self._settings.default_tts_voice_id)

        try:
            async for sentence in token_stream_to_sentences(token_iter()):
                if self._interrupt_event and self._interrupt_event.is_set():
                    turns_interrupted.inc()
                    break

                text_to_speak = sentence

                async def single_text(text=text_to_speak) -> AsyncIterator[str]:
                    yield text

                async for chunk in self._tts.synthesize_stream(single_text(), voice_id=voice_id):
                    if self._interrupt_event and self._interrupt_event.is_set():
                        turns_interrupted.inc()
                        break
                    if first_audio_time is None:
                        first_audio_time = time.monotonic()
                        metrics.tts_first_byte_ms = (first_audio_time - llm_start) * 1000
                        metrics.e2e_ms = (first_audio_time - turn_start) * 1000
                        tts_first_byte_seconds.observe(first_audio_time - llm_start)
                        e2e_turn_latency_seconds.observe(first_audio_time - turn_start)
                    await self._maybe_await(callbacks.on_audio(chunk))
        except Exception as exc:
            logger.error("pipeline_tts_error", session_id=str(session_id), error=str(exc))
            await self._maybe_await(callbacks.on_error("tts_error", str(exc)))

        if assistant_text:
            self._conversation.add_assistant_message(session_id, assistant_text)
            await self._sessions.save_assistant_message(session_id, assistant_text)

        await self._sessions.save_turn_metrics(session_id, metrics)
        await self._sessions.commit()
        await self._maybe_await(callbacks.on_metrics(metrics))
        turns_completed.inc()

        await self._sessions.clear_interrupt(session_id)
        await self._sessions.update_phase(session_id, SessionPhase.LISTENING)

    async def interrupt(self, session_id: UUID) -> None:
        await self._sessions.set_interrupt(session_id)
        if self._interrupt_event:
            self._interrupt_event.set()
        logger.info("pipeline_interrupted", session_id=str(session_id))

    @staticmethod
    async def _maybe_await(result: Any) -> None:
        if asyncio.iscoroutine(result):
            await result
