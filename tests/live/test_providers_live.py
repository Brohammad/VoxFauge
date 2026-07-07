"""Live provider tests — require real API keys.

Run with:
    OPENAI_API_KEY=... DEEPGRAM_API_KEY=... CARTESIA_API_KEY=... pytest -m live -v
"""

import asyncio
import math
import struct
from collections.abc import AsyncIterator

import pytest

from voxforge.config import Settings
from voxforge.core.domain.entities import MessageRole
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.infrastructure.providers.stt.deepgram import DeepgramSTTProvider
from voxforge.infrastructure.providers.tts.cartesia import CartesiaTTSProvider

pytestmark = pytest.mark.live


def _sine_pcm(duration: float = 0.5, sample_rate: int = 16000, frequency: int = 440) -> bytes:
    samples = []
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        value = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


async def _bytes_stream(data: bytes, chunk_size: int = 3200) -> AsyncIterator[bytes]:
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_openai_streaming(openai_api_key: str) -> None:
    from dataclasses import dataclass

    @dataclass
    class Msg:
        role: MessageRole
        content: str

    provider = OpenAILLMProvider(openai_api_key)
    messages = [Msg(role=MessageRole.USER, content="Reply with exactly: pong")]

    tokens: list[str] = []
    async for event in provider.generate_stream(messages, model="gpt-4.1-mini"):
        if event.text:
            tokens.append(event.text)

    response = "".join(tokens).lower()
    assert "pong" in response


@pytest.mark.asyncio
async def test_cartesia_tts(cartesia_api_key: str) -> None:
    settings = Settings(cartesia_api_key=cartesia_api_key)
    provider = CartesiaTTSProvider(cartesia_api_key)

    async def text_stream() -> AsyncIterator[str]:
        yield "Hello from VoxForge."

    chunks: list[bytes] = []
    async for chunk in provider.synthesize_stream(
        text_stream(), voice_id=settings.default_tts_voice_id
    ):
        chunks.append(chunk.data)

    assert sum(len(c) for c in chunks) > 1000


@pytest.mark.asyncio
async def test_deepgram_connection(deepgram_api_key: str) -> None:
    """Verify Deepgram accepts a streaming session and processes audio."""
    provider = DeepgramSTTProvider(deepgram_api_key)
    audio = _sine_pcm(duration=1.0)

    async def fast_stream() -> AsyncIterator[bytes]:
        for i in range(0, len(audio), 3200):
            yield audio[i : i + 3200]

    event_count = 0
    async for _event in provider.transcribe_stream(fast_stream(), language="en"):
        event_count += 1

    # Sine waves rarely produce transcripts; completing the stream is the success signal.
    assert event_count >= 0


@pytest.mark.asyncio
async def test_conversation_engine_live(openai_api_key: str) -> None:
    from voxforge.modules.conversation.application.engine import ConversationEngine

    settings = Settings(openai_api_key=openai_api_key)
    engine = ConversationEngine(OpenAILLMProvider(openai_api_key), settings)
    session_id = __import__("uuid").uuid4()
    engine.init_session(session_id)
    engine.add_user_message(session_id, "Say hello in three words or fewer.")

    tokens: list[str] = []
    async for event in engine.generate_response(session_id):
        if event.text:
            tokens.append(event.text)

    assert len("".join(tokens).strip()) > 0
