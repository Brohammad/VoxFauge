# VoxForge Project Metrics

> Single source of truth for repository engineering metrics.  
> Last updated: 2026-07-09  
> Regenerate: `python scripts/generate_project_metrics.py`

## Summary

| Metric | Value |
|--------|------:|
| Application modules | 17 |
| REST endpoints | 58 |
| WebSocket endpoints | 1 |
| Tests collected | 154 |
| Line coverage (`src/voxforge`) | n/a |
| ADRs | 4 |
| Architecture documents | 17 |
| Benchmark documents | 1 |

## Application modules (17)

- `agent_config`
- `agent_orchestrator`
- `alerts`
- `auth`
- `conversation`
- `dashboard`
- `evaluation`
- `livekit_gateway`
- `mcp_tool_router`
- `memory`
- `onboarding`
- `outcomes`
- `replay`
- `session_manager`
- `stt`
- `tts`
- `voice_gateway`

## API surface

| Transport | Count | Entry points |
|-----------|------:|--------------|
| REST | 58 | `/api/v1/*` routers |
| WebSocket | 1 | `/api/v1/ws/voice` |

## Tests

Run: `PYTHONPATH=. pytest -v`

| Category | Location |
|----------|----------|
| Unit | `tests/unit/` |
| Integration | `tests/integration/` |

## Architecture decision records (4)

- [ADR-001-programmatic-voice-pipeline-runner.md](adr/ADR-001-programmatic-voice-pipeline-runner.md)
- [ADR-002-onboarding-session-lifecycle.md](adr/ADR-002-onboarding-session-lifecycle.md)
- [ADR-003-mcp-runtime-discovery.md](adr/ADR-003-mcp-runtime-discovery.md)
- [ADR-004-livekit-transport-adapter.md](adr/ADR-004-livekit-transport-adapter.md)

## Architecture documents (17)

- [agent-config-versioning.md](architecture/agent-config-versioning.md)
- [agent-orchestrator.md](architecture/agent-orchestrator.md)
- [alerts.md](architecture/alerts.md)
- [authentication.md](architecture/authentication.md)
- [ci-hardening.md](architecture/ci-hardening.md)
- [dashboard.md](architecture/dashboard.md)
- [evaluation-engine.md](architecture/evaluation-engine.md)
- [livekit-integration.md](architecture/livekit-integration.md)
- [livekit-webrtc.md](architecture/livekit-webrtc.md)
- [mcp-runtime-discovery.md](architecture/mcp-runtime-discovery.md)
- [mcp-tool-router.md](architecture/mcp-tool-router.md)
- [memory.md](architecture/memory.md)
- [observability.md](architecture/observability.md)
- [onboarding-voice-pipeline.md](architecture/onboarding-voice-pipeline.md)
- [outcomes.md](architecture/outcomes.md)
- [replay.md](architecture/replay.md)
- [voice-pipeline.md](architecture/voice-pipeline.md)

## Benchmarks (1)

- [onboarding.md](benchmarks/onboarding.md)

## Supported providers

| Capability | Providers |
|------------|-----------|
| STT | `deepgram`, `mock` |
| LLM | `openai`, `mock` |
| TTS | `cartesia`, `mock` |
| Embeddings | `openai` (`text-embedding-3-small`) |
| WebRTC transport | LiveKit |
| Voice transport | WebSocket, LiveKit WebRTC |

## Supported MCP servers

MCP servers are **runtime-discovered** from `MCP_SERVERS_CONFIG` (stdio transport). Static
tool metadata is used as a degraded fallback when discovery fails. Inspect live status via:

- `GET /api/v1/tools/mcp/health`
- `GET /api/v1/tools/mcp/servers`

No servers are hardcoded in the repository; operators declare servers in environment config.

## Phase status

| Phase | Status |
|-------|--------|
| Phase 0 — Stabilization | Complete |
| Phase 1 — Onboarding voice pipeline | Complete |
| Phase 2 — CI hardening | Complete |
| Phase 3 — MCP runtime discovery | Complete |
| Phase 4 — LiveKit transport adapter | Complete |
| Phase 5 — Public deployment | Complete |
| Production hardening & load testing | Planned |
