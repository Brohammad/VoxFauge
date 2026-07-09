# CI Hardening

Phase 2 changes to keep quality gates deterministic without external API keys.

## PostgreSQL + pgvector

CI uses `pgvector/pgvector:pg16` (matching `docker-compose.yml`) and runs
`alembic upgrade head` before tests. The integration test
`test_memory_repository_postgres_vector_search` exercises the real pgvector
`CAST(... AS vector)` similarity path — no skip/degraded branch in CI.

## Voice pipeline E2E

| Test | Transport | Location |
|------|-----------|----------|
| Programmatic turn artifacts | `run_text_turn` via onboarding API | `tests/integration/test_voice_pipeline_e2e.py` |
| WebSocket session lifecycle | `/api/v1/ws/voice` start/end with mock providers | `tests/integration/test_voice_pipeline_e2e.py` |

Full WebSocket audio turns (STT streaming) are validated manually via `scripts/test_voice_ws.py`.
The mock STT provider finalizes after the first audio chunk to keep local WS tests responsive.

## Coverage

`pytest --cov=voxforge` produces terminal and XML reports. XML is uploaded as a
GitHub Actions artifact (`coverage-xml`).

## Benchmark (non-blocking)

Job `benchmark-onboarding` runs after tests with `continue-on-error: true`.
Results uploaded as `benchmark-onboarding.json` for trend comparison against
`docs/benchmarks/onboarding.md`.

## Required CI environment

```
STT_PROVIDER=mock
LLM_PROVIDER=mock
TTS_PROVIDER=mock
MEMORY_ENABLED=false
EVALUATION_HALLUCINATION_ENABLED=false
TOOLS_ENABLED=false
```
