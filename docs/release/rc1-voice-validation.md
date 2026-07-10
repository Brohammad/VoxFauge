# RC-1 Voice Stack Validation Report

**Release:** RC-1  
**Date:** 2026-07-10  
**Providers:** mock (CI/default), live (opt-in via `scripts/run_live_tests.sh`)

## Automated coverage

| Capability | Test location | Status |
|------------|---------------|--------|
| WebSocket start/end | `tests/integration/test_voice_pipeline_e2e.py`, E2E QA | ✅ Pass |
| Programmatic text turn (onboarding) | `tests/unit/test_voice_pipeline_text_turn.py`, benchmarks | ✅ Pass |
| STT skip + LLM + TTS pipeline | `tests/feature/test_customer_support_flow.py` | ✅ Pass |
| Knowledge injection in conversation | `tests/unit/test_conversation_engine_knowledge.py` | ✅ Pass |
| Memory retrieval | `tests/integration/test_memory.py` | ✅ Pass |
| Tool execution | `tests/integration/test_tools.py` | ✅ Pass |
| Handoff + ticket | `tests/integration/test_handoff.py`, browser tests | ✅ Pass |
| Replay + evaluation | `tests/integration/test_replay.py`, `test_evaluation_integration.py` | ✅ Pass |
| Provider failure recovery | `tests/failure/test_provider_failures.py` | ✅ Pass |
| LiveKit token API | `tests/integration/test_livekit_session_runner.py` | ✅ Pass (mock config) |
| Live Deepgram/OpenAI/Cartesia | `tests/live/` | ⚠ Skipped without API keys |

## Manual validation required (RC-1)

| Capability | Procedure | RC-1 status |
|------------|-----------|-------------|
| Microphone capture | Browser + WebSocket client | Not automated |
| Barge-in | Live session interrupt | Not tested |
| LiveKit WebRTC audio | `/examples/livekit` + LiveKit Cloud | Requires operator keys |
| Disconnect/reconnect | `scripts/test_voice_ws.py` | Manual script available |

## Recommendation

RC-1 is **approved for portfolio and design-partner pilots with mock providers**. Enterprise voice pilots should run `scripts/run_live_tests.sh` and manual LiveKit validation before GA.
