# ADR-004: LiveKit Transport Adapter

## Status

Accepted (2026-07-10)

## Context

Phase 4 requires WebRTC voice via LiveKit without duplicating the production voice stack.
Token generation and a browser demo existed, but no server worker bridged room audio into
`VoicePipelineService`. WebSocket transport must remain unchanged and API contracts must stay
backward compatible.

## Decision

Treat LiveKit as a **transport adapter only**:

```text
LiveKit Room → LiveKit Worker → LiveKitSessionRunner → VoicePipelineService
```

### Components

| Layer | Responsibility |
|-------|----------------|
| `LiveKitTokenService` | Participant JWT + room naming (`voxforge-{session_id}`) |
| `LiveKitDispatchService` | Optional agent dispatch on token creation (graceful degrade) |
| `infrastructure/livekit/worker.py` | `livekit-agents` job entrypoint (separate process) |
| `LiveKitSessionRunner` | Room lifecycle, audio ingress, barge-in, reconnection hooks |
| `audio_bridge` / `LiveKitAudioPublisher` | PCM format conversion; no business logic |
| `build_voice_pipeline_bundle` | Shared pipeline wiring for WebSocket and LiveKit |

### Non-goals

- No duplicate STT/LLM/TTS/orchestration path
- No replacement of WebSocket transport
- No breaking changes to existing REST/WebSocket APIs

### Session synchronization

- Room name encodes `session_id` for correlation with `SessionManager`
- Worker calls `activate_session` / `resume_session` before pipeline turns
- Heartbeats reuse existing Redis session state TTL

### Barge-in

When participant audio arrives while session phase is `SPEAKING`, the runner calls
`VoicePipelineService.interrupt()` — same primitive as WebSocket `interrupt` control messages.

### Reconnection

- Participant disconnect increments metrics and logs disconnect reason
- `livekit_reconnect_grace_seconds` (default 30s) before worker shutdown
- `resume_session` on participant rejoin within the same job

### Observability

Prometheus counters/histograms:

- `voxforge_livekit_room_lifecycle_total`
- `voxforge_livekit_participant_events_total`
- `voxforge_livekit_barge_in_total`
- `voxforge_livekit_reconnection_attempts_total`
- `voxforge_livekit_dispatch_total`
- `voxforge_livekit_audio_frame_latency_seconds`
- `voxforge_livekit_streaming_latency_seconds`

OpenTelemetry spans: `livekit.room.join`, `livekit.session.prepare`, `livekit.session.reconnect`.

### Performance target

Transport bridge targets **<50 ms** additional ingress overhead (measured via
`voxforge_livekit_audio_frame_latency_seconds` histogram buckets topping at 50 ms).

## Consequences

### Positive

- Single pipeline source of truth for WebSocket, programmatic onboarding, and LiveKit
- Worker crash isolates to one room job; API process unaffected
- Dispatch failures do not block token issuance

### Negative

- Requires separate worker process (`make livekit-worker`) alongside the API
- Full multi-turn reconnect with new audio tracks is limited to grace-period rejoin within one job

### Future transports

The same adapter pattern (transport runner → shared `VoicePipelineService`) applies to Twilio,
SIP, and raw WebRTC gateways without changing domain modules.

## References

- `docs/architecture/livekit-integration.md`
- ADR-001 (programmatic pipeline runner)
- `src/voxforge/modules/livekit_gateway/application/session_runner.py`
