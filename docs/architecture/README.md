# Architecture Documentation

VoxForge is a **modular monolith** built with Clean Architecture: `api/` → `modules/` → `core/`, with infrastructure adapters in `infrastructure/`.

## System overview

```text
Client
  → Transport (WebSocket / LiveKit WebRTC / REST onboarding)
  → VoicePipelineService
  → Agent Orchestrator (LangGraph)
  → MCP Tool Router + Knowledge RAG + Memory
  → Evaluation Engine
  → Replay / Handoff / Dashboard
```

[Diagrams (Mermaid)](../portfolio/architecture-diagrams.md) · [Deployment topology](../deployment/architecture.md)

---

## Core pipeline

| Document | Topic |
|----------|-------|
| [voice-pipeline.md](voice-pipeline.md) | STT → agent → TTS orchestration |
| [onboarding-voice-pipeline.md](onboarding-voice-pipeline.md) | Programmatic onboarding API |
| [agent-orchestrator.md](agent-orchestrator.md) | LangGraph multi-agent graph |
| [evaluation-engine.md](evaluation-engine.md) | Per-turn quality and latency scoring |

## Transport

| Document | Topic |
|----------|-------|
| [livekit-integration.md](livekit-integration.md) | LiveKit gateway integration |
| [livekit-webrtc.md](livekit-webrtc.md) | WebRTC browser audio path |

## Data & intelligence

| Document | Topic |
|----------|-------|
| [knowledge-base.md](knowledge-base.md) | Document ingestion, RAG, citations |
| [memory.md](memory.md) | Semantic memory and summarization |
| [mcp-tool-router.md](mcp-tool-router.md) | Builtin + MCP tools |
| [mcp-runtime-discovery.md](mcp-runtime-discovery.md) | MCP server discovery at startup |

## Operations & trust

| Document | Topic |
|----------|-------|
| [dashboard.md](dashboard.md) | Operator UI and analytics API |
| [replay.md](replay.md) | Session replay and signed links |
| [human-handoff.md](human-handoff.md) | Escalation queue and ticketing hooks |
| [outcomes.md](outcomes.md) | Outcome extraction and trends |
| [alerts.md](alerts.md) | Regression alert thresholds |
| [metrics.md](metrics.md) | Prometheus metrics |
| [observability.md](observability.md) | OpenTelemetry and logging |

## Security & reliability

| Document | Topic |
|----------|-------|
| [authentication.md](authentication.md) | JWT, API keys, SAML SSO |
| [rate-limiting.md](rate-limiting.md) | Per-route rate limits |
| [session-consistency.md](session-consistency.md) | Redis + Postgres session state |
| [integrity-concurrency.md](integrity-concurrency.md) | Concurrency controls |
| [failure-recovery.md](failure-recovery.md) | Failure modes and recovery |
| [ci-hardening.md](ci-hardening.md) | CI quality gates |

## Configuration

| Document | Topic |
|----------|-------|
| [agent-config-versioning.md](agent-config-versioning.md) | Policy presets and version history |
| [customer-support-tools.md](customer-support-tools.md) | Support tool integrations |

## Architecture decisions (ADRs)

Significant design choices are recorded in [../adr/README.md](../adr/README.md).
