# Onboarding Pipeline Benchmark

Baseline measurements for the programmatic onboarding sample-call path introduced in
Phase 1 (ADR-001). Use this document to track regressions before/after LiveKit integration
and other latency optimizations.

## Reproduce

```bash
make benchmark-onboarding
```

JSON output (for CI artifacts and diffs):

```bash
make benchmark-onboarding-json
python scripts/benchmark_onboarding.py --iterations 20 --warmup 3 --json
```

Memory retrieval included:

```bash
make benchmark-onboarding-memory
```

## Methodology

| Parameter | Value |
|-----------|-------|
| Scenario | `billing_contact_change` scripted sample call |
| Pipeline | `ProgrammaticPipelineRunner` → `VoicePipelineService.run_text_turn()` |
| Providers | Mock STT, LLM, TTS (no external API keys) |
| Database | In-memory SQLite |
| Session state | fakeredis |
| Warmup | 3 iterations (discarded) |
| Measured iterations | 20 |
| External provider latency | **Excluded** — mocks return immediately |

### Metrics collected

| Metric | Definition |
|--------|------------|
| **Wall clock** | Total time for `run_scripted_turn()` including session I/O, evaluation, outcomes |
| **Pipeline e2e** | `TurnMetrics.e2e_ms` — transcript to first TTS audio byte inside `_process_turn()` |
| **Pipeline overhead** | `wall_clock_ms - pipeline_e2e_ms` — persistence, evaluation, orchestration outside provider streaming |
| **LLM first token** | `TurnMetrics.llm_first_token_ms` |
| **TTS first byte** | `TurnMetrics.tts_first_byte_ms` |
| **Evaluation (isolated)** | Separate `EvaluationEngine.evaluate_turn()` call on same turn data |
| **Memory retrieval** | `MemoryService.retrieve_context()` with fixed local embedder (`--memory` only) |

## Baseline (2026-07-10)

**Environment**

| Field | Value |
|-------|-------|
| Machine | Apple Silicon Mac (arm64) |
| OS | macOS 26.5 |
| Python | 3.14.5 |
| Providers | mock / mock / mock |
| Target (platform overhead) | < 800 ms excluding provider latency |

### Without memory

| Metric | Mean (ms) | p50 (ms) | p95 (ms) |
|--------|-----------|----------|----------|
| Wall clock | 7.09 | 6.87 | 8.36 |
| Pipeline e2e | 1.10 | 1.09 | 1.18 |
| Pipeline overhead | 5.99 | 5.72 | 7.21 |
| LLM first token | 0.55 | 0.54 | 0.58 |
| TTS first byte | 0.56 | 0.55 | 0.59 |
| Evaluation (isolated) | 1.61 | 1.53 | 2.24 |
| Memory retrieval | N/A | — | — |

### With memory (fixed local embedder, SQLite)

| Metric | Mean (ms) | p50 (ms) | p95 (ms) |
|--------|-----------|----------|----------|
| Wall clock | 10.16 | 10.37 | 10.55 |
| Pipeline e2e | 2.42 | 2.34 | 2.98 |
| Pipeline overhead | 7.75 | 7.99 | 8.25 |
| LLM first token | 1.18 | 1.13 | 1.39 |
| TTS first byte | 1.20 | 1.14 | 1.41 |
| Evaluation (isolated) | 1.61 | 1.53 | 2.22 |
| Memory retrieval | 0.77 | 0.72 | 0.96 |

**Interpretation:** Platform overhead is **~6–8 ms p50** on mock providers — well under the
800 ms engineering target. Dominant cost today is session persistence and evaluation writes,
not voice streaming.

## Current limitations

1. **Mock providers only** — does not measure Deepgram, OpenAI, or Cartesia network latency.
2. **Programmatic path** — STT is skipped; WebSocket + audio streaming not benchmarked here.
3. **SQLite** — production uses PostgreSQL + Redis; absolute wall-clock numbers will differ.
4. **Memory benchmark** — uses fixed-dimension local embedder, not OpenAI embeddings or pgvector.
5. **Single script** — only `billing_contact_change`; multi-turn sessions not covered.
6. **No concurrency** — sequential iterations; load behavior not represented.

## Comparison workflow

After optimizations:

```bash
python scripts/benchmark_onboarding.py --iterations 20 --warmup 3 --json > /tmp/bench-after.json
```

Compare `latency_ms.pipeline_overhead.p95` and `latency_ms.wall_clock.p95` against this baseline.

## Related docs

- [ADR-001: Programmatic Voice Pipeline Runner](../adr/ADR-001-programmatic-voice-pipeline-runner.md)
- [Onboarding voice pipeline architecture](../architecture/onboarding-voice-pipeline.md)
