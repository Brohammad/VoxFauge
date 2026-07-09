"""Audio format conversion between LiveKit frames and the voice pipeline."""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass

from voxforge.core.domain.events import AudioChunk
from voxforge.infrastructure.observability.metrics import livekit_audio_frame_latency_seconds

PIPELINE_SAMPLE_RATE = 16_000
PIPELINE_CHANNELS = 1


@dataclass(frozen=True)
class PcmFrame:
    data: bytes
    sample_rate: int
    num_channels: int


def _resample_pcm16(data: bytes, src_rate: int, dst_rate: int, num_channels: int) -> bytes:
    if src_rate == dst_rate:
        return data
    if num_channels != 1:
        # Downmix stereo to mono before resampling.
        samples = struct.unpack(f"<{len(data) // 2}h", data)
        mono = []
        for i in range(0, len(samples), num_channels):
            mono.append(sum(samples[i : i + num_channels]) // num_channels)
        data = struct.pack(f"<{len(mono)}h", *mono)
        num_channels = 1
    if src_rate % dst_rate == 0:
        step = src_rate // dst_rate
        samples = struct.unpack(f"<{len(data) // 2}h", data)
        downsampled = samples[::step]
        return struct.pack(f"<{len(downsampled)}h", *downsampled)
    ratio = dst_rate / src_rate
    samples = struct.unpack(f"<{len(data) // 2}h", data)
    out_len = int(len(samples) * ratio)
    if out_len == 0:
        return b""
    out = []
    for i in range(out_len):
        src_idx = i / ratio
        left = int(src_idx)
        right = min(left + 1, len(samples) - 1)
        frac = src_idx - left
        out.append(int(samples[left] * (1 - frac) + samples[right] * frac))
    return struct.pack(f"<{len(out)}h", *out)


def frame_to_pipeline_pcm(
    frame_data: bytes,
    *,
    sample_rate: int,
    num_channels: int,
    received_at: float | None = None,
) -> bytes:
    """Convert a LiveKit PCM frame to 16 kHz mono for STT ingestion."""
    if received_at is not None:
        livekit_audio_frame_latency_seconds.observe(max(0.0, time.monotonic() - received_at))
    pcm = _resample_pcm16(frame_data, sample_rate, PIPELINE_SAMPLE_RATE, num_channels)
    return pcm


def chunk_to_livekit_frame(
    chunk: AudioChunk,
    *,
    target_sample_rate: int = PIPELINE_SAMPLE_RATE,
    target_channels: int = PIPELINE_CHANNELS,
) -> PcmFrame:
    """Convert pipeline TTS output into a frame suitable for LiveKit publish."""
    data = chunk.data
    src_rate = chunk.sample_rate or PIPELINE_SAMPLE_RATE
    if src_rate != target_sample_rate:
        data = _resample_pcm16(data, src_rate, target_sample_rate, target_channels)
    return PcmFrame(
        data=data,
        sample_rate=target_sample_rate,
        num_channels=target_channels,
    )
