# ADR-001: Programmatic Voice Pipeline Runner

## Status

Accepted (2026-07-10)

## Context

Onboarding sample calls previously wrote hardcoded transcripts and metrics directly to the
database. That bypassed `VoicePipelineService`, producing evaluation and replay data that did
not reflect production voice behavior.

We need a deterministic, CI-friendly path that exercises the same STT-skipped-but-otherwise
identical turn pipeline used in production (LLM streaming, TTS streaming, evaluation,
outcomes, memory hooks) without requiring a WebSocket client or live audio.

## Decision

Introduce a **Programmatic Pipeline Runner** that:

1. Adds `VoicePipelineService.run_text_turn()` to invoke `_process_turn()` with a text
   transcript and `stt_ms=0`, skipping audio/STT.
2. Wraps the pipeline in `ProgrammaticPipelineRunner` (infrastructure adapter) behind the
   `OnboardingPipelineRunner` port.
3. Drives onboarding via scripted scenarios in `sample_scripts.py`.
4. Creates a **new session on every** `POST /onboarding/run-sample-call` invocation.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| WebSocket E2E client for onboarding | Flaky in CI, slower, harder to debug; better suited to manual/live E2E scripts |
| Keep simulated DB writes | Duplicates pipeline logic; weak interview story; divergent metrics |
| Fork onboarding-specific mini-pipeline | Violates DRY; two code paths to maintain |

## Consequences

**Positive**

- Onboarding metrics, evaluations, outcomes, and replay all originate from production code.
- Tests run with mock providers (no API keys).
- OpenTelemetry spans and Prometheus histograms cover the full sample-call path.

**Negative / trade-offs**

- `run_text_turn()` is not identical to WebSocket transport (no STT, no barge-in during sample).
- Mock LLM includes a billing-contact keyword branch for deterministic CI outcomes.

## Future Migration

- Add `scripts/e2e_voice_ws.py` for full WebSocket transport validation (Phase 2+).
- Wire LiveKit audio into the same `VoicePipelineService` path (separate ADR).
- Replace keyword-based mock LLM responses with fixture-driven mock configuration if more
  scripts are added.
