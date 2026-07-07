import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import websockets

from voxforge.core.domain.events import TranscriptEvent
from voxforge.core.exceptions import ProviderError
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramSTTProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        *,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptEvent]:
        if not self._api_key:
            raise ProviderError("deepgram", "API key not configured")

        params = {
            "encoding": "linear16",
            "sample_rate": "16000",
            "channels": "1",
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
        }
        if language:
            params["language"] = language
        else:
            params["detect_language"] = "true"

        url = f"{DEEPGRAM_WS_URL}?{urlencode(params)}"
        headers = {"Authorization": f"Token {self._api_key}"}

        try:
            async with websockets.connect(url, additional_headers=headers) as ws:
                send_task = asyncio.create_task(self._send_audio(ws, audio_stream))
                try:
                    async for message in ws:
                        if isinstance(message, bytes):
                            continue
                        event = self._parse_message(message)
                        if event is not None:
                            yield event
                finally:
                    send_task.cancel()
                    try:
                        await send_task
                    except asyncio.CancelledError:
                        pass
                    await ws.send(json.dumps({"type": "CloseStream"}))
        except websockets.exceptions.WebSocketException as exc:
            logger.error("deepgram_ws_error", error=str(exc))
            raise ProviderError("deepgram", str(exc)) from exc

    async def _send_audio(self, ws, audio_stream: AsyncIterator[bytes]) -> None:
        try:
            async for chunk in audio_stream:
                await ws.send(chunk)
        except asyncio.CancelledError:
            pass

    def _parse_message(self, raw: str) -> TranscriptEvent | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        if data.get("type") != "Results":
            return None

        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])
        if not alternatives:
            return None

        alt = alternatives[0]
        transcript = alt.get("transcript", "").strip()
        if not transcript:
            return None

        is_final = data.get("is_final", False)
        confidence = alt.get("confidence")
        detected_language = data.get("metadata", {}).get("detected_language")

        return TranscriptEvent(
            text=transcript,
            is_partial=not is_final,
            confidence=confidence,
            language=detected_language,
        )
