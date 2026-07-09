# Phase 1 Architecture Review: Real Voice-Backed Onboarding

## Summary

Onboarding sample calls now execute through the production `VoicePipelineService` via a
programmatic text-turn entry point, replacing simulated transcript/metric writes.

## Why This Design

- **Single code path**: Evaluation, outcomes, memory hooks, and turn metrics are produced by
  `_process_turn()` — the same method WebSocket voice uses after STT.
- **Determinism**: Scripted transcripts + mock providers keep CI stable without API keys.
- **Interview clarity**: "Onboarding calls the real pipeline; only STT is skipped because input
  is text."

## Alternatives Considered

1. **WebSocket E2E** — full transport fidelity but unsuitable as the default onboarding path.
2. **Simulated persistence** — minimal diff but maintains a fake second pipeline.
3. **Onboarding-only slim pipeline** — faster but duplicates orchestration logic.

## Trade-offs

| Gain | Cost |
|------|------|
| Production-faithful metrics | Sample calls skip STT and barge-in |
| CI-friendly mocks | Mock LLM has a billing-keyword branch for scripted success |
| New session per run | Outcome session counts rise with repeated sample calls |

## Technical Debt Introduced

- `run_text_turn()` exposes a package-private turn processor publicly; acceptable as a narrow
  extension point documented in ADR-001.
- Mock LLM keyword routing is pragmatic, not a general fixture framework.
- Onboarding still uses the latest run row rather than immutable run-per-step history.

## Future Migration

- Phase 2: pgvector in CI, optional WebSocket E2E gate.
- LiveKit: route WebRTC audio into `run_listening()` (STT path), not `run_text_turn()`.
- Prompt/agent-config version pins on sample-call sessions for A/B comparisons.

## Performance Notes

- Programmatic turns skip STT; platform overhead target < 800 ms excluding provider latency.
- `onboarding_sample_call_duration_seconds` histogram added for wall-clock tracking.
- All paths remain async; no blocking I/O on the event loop.

## Observability

| Signal | Name |
|--------|------|
| Span | `onboarding.sample_call`, `voice_pipeline.run_text_turn`, `onboarding.pipeline_runner.run_scripted_turn` |
| Counter | `voxforge_onboarding_steps_total{status=test_call_failed}` |
| Histogram | `voxforge_onboarding_sample_call_duration_seconds` |
| Logs | `onboarding_sample_call_passed`, `onboarding_sample_call_failed`, `pipeline_text_turn_completed` |
