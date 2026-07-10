# VoxForge Testing Strategy

## Testing pyramid

```
        ┌─────────┐
        │  E2E    │  tests/e2e/ — deployment smoke, full platform paths
        ├─────────┤
        │ Feature │  tests/feature/ — business flows (support, KB, replay)
        ├─────────┤
        │ Integr. │  tests/integration/ — API + DB + Redis
        ├─────────┤
        │  Unit   │  tests/unit/ — domain logic, policies, helpers
        └─────────┘
```

Additional suites:

| Suite | Path | Purpose |
|-------|------|---------|
| Failure | `tests/failure/` | Redis/DB outages, auth errors, concurrency |
| Live | `tests/live/` | Real provider smoke (skipped without API keys) |
| Benchmarks | `scripts/benchmark_*.py` | Latency baselines for CI |

## Coverage targets

| Scope | Target | CI gate |
|-------|--------|---------|
| Overall | 85% | 70% (ratchet upward) |
| Business logic (`modules/`, `core/`) | 90% | reported in markdown artifact |

Generate reports locally:

```bash
make test-cov
# or
python scripts/generate_coverage_report.py --fail-under=70
```

Artifacts: `coverage.xml`, `htmlcov/`, `docs/testing/coverage-report.md`

## Mock providers

CI and local tests default to mock providers (no API keys):

- `STT_PROVIDER=mock`
- `LLM_PROVIDER=mock`
- `TTS_PROVIDER=mock`
- `EMBEDDING_PROVIDER=mock`

Integration tests autouse `mock_voice_stack` (see `tests/integration/conftest.py`).

## Running locally

```bash
pip install -e ".[dev,livekit]"
make test              # full suite
make test-unit         # unit only
make test-integration  # integration only
make test-feature      # feature flows
make test-failure      # failure modes
make test-e2e          # e2e smoke
```

With Postgres + Redis (matches CI):

```bash
docker compose up -d postgres redis
export DATABASE_URL=postgresql+asyncpg://voxforge:voxforge@localhost:5432/voxforge
export REDIS_URL=redis://localhost:6379/0
alembic upgrade head
pytest tests/ -v
```

## Known limitations

- LiveKit worker process (`infrastructure/livekit/worker.py`) is not started in CI
- Knowledge background worker runs inline when `KNOWLEDGE_WORKER_ENABLED=false`
- Load tests (`scripts/load/`) require a running server; not executed in default CI
- Live provider tests in `tests/live/` require `.env` API keys

## CI pipeline

See [coverage.md](./coverage.md) and `.github/workflows/ci.yml`:

1. Lint (`ruff`)
2. Migrations (`alembic upgrade head`)
3. Unit → Integration → Feature → Failure → E2E
4. Full suite with coverage gate (70%)
5. Benchmarks (onboarding, knowledge base)
6. Eval quality gate
7. Docker production build
