#!/usr/bin/env python3
"""Manual WebSocket voice test client.

Sends synthetic PCM audio over the VoxForge voice WebSocket and prints responses.

Usage:
    python scripts/test_voice_ws.py [--url ws://localhost:8000/api/v1/ws/voice]
"""

import argparse
import asyncio
import json
import math
import struct
import sys

import websockets

SAMPLE_RATE = 16000
DURATION_SECONDS = 2
FREQUENCY = 440


def generate_sine_pcm(duration: float = DURATION_SECONDS, frequency: int = FREQUENCY) -> bytes:
    """Generate 16-bit mono PCM sine wave at 16kHz."""
    samples = []
    for i in range(int(SAMPLE_RATE * duration)):
        t = i / SAMPLE_RATE
        value = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


async def run_test(ws_url: str) -> None:
    print(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url) as ws:
        start_msg = json.dumps({
            "type": "start",
            "config": {"language": "en"},
        })
        await ws.send(start_msg)
        print("Sent start message")

        response = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(response)
        print(f"Server: {data}")

        if data.get("type") != "started":
            print("Failed to start session")
            return

        session_id = data["session_id"]
        print(f"Session ID: {session_id}")

        audio = generate_sine_pcm()
        chunk_size = 3200
        for i in range(0, len(audio), chunk_size):
            await ws.send(audio[i : i + chunk_size])
            await asyncio.sleep(0.1)

        print("Audio sent, waiting for responses (10s timeout)...")

        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=10)
                if isinstance(msg, bytes):
                    print(f"Received audio chunk: {len(msg)} bytes")
                else:
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    if msg_type == "transcript":
                        partial = "partial" if data.get("partial") else "final"
                        print(f"  [{partial}] {data.get('text')}")
                    elif msg_type == "response":
                        print(f"  [token] {data.get('token')}", end="", flush=True)
                    elif msg_type == "metric":
                        print(f"\n  [metrics] {data}")
                    elif msg_type == "error":
                        print(f"  [error] {data}")
                        break
                    else:
                        print(f"  [{msg_type}] {data}")
        except asyncio.TimeoutError:
            print("\nTimeout waiting for responses")

        await ws.send(json.dumps({"type": "end"}))
        try:
            end_resp = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"End response: {end_resp}")
        except asyncio.TimeoutError:
            pass

        print("Done.")


def main():
    parser = argparse.ArgumentParser(description="VoxForge voice WebSocket test client")
    parser.add_argument(
        "--url",
        default="ws://localhost:8000/api/v1/ws/voice",
        help="WebSocket URL",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_test(args.url))
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(0)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
