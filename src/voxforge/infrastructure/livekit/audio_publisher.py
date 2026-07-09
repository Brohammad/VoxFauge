"""Publish pipeline TTS audio to a LiveKit room."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from voxforge.core.domain.events import AudioChunk
from voxforge.infrastructure.livekit.audio_bridge import (
    PIPELINE_SAMPLE_RATE,
    chunk_to_livekit_frame,
)

if TYPE_CHECKING:
    from livekit import rtc


class AudioPublisher(Protocol):
    async def publish_chunk(self, chunk: AudioChunk) -> None: ...


class LiveKitAudioPublisher:
    """Publishes PCM frames to a LiveKit ``AudioSource``."""

    def __init__(
        self,
        source: rtc.AudioSource,
        *,
        sample_rate: int = PIPELINE_SAMPLE_RATE,
    ) -> None:
        from livekit import rtc as _rtc

        self._rtc = _rtc
        self._source = source
        self._sample_rate = sample_rate
        self._lock = asyncio.Lock()

    async def publish_chunk(self, chunk: AudioChunk) -> None:
        pcm = chunk_to_livekit_frame(chunk, target_sample_rate=self._sample_rate)
        frame = self._rtc.AudioFrame(
            data=pcm.data,
            sample_rate=pcm.sample_rate,
            num_channels=pcm.num_channels,
            samples_per_channel=len(pcm.data) // (2 * pcm.num_channels),
        )
        async with self._lock:
            await self._source.capture_frame(frame)


class NullAudioPublisher:
    """No-op publisher for tests."""

    async def publish_chunk(self, chunk: AudioChunk) -> None:
        return None
