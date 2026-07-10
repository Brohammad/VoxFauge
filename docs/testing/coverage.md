# Coverage

## Targets

| Scope | Production target | Current CI gate |
|-------|-------------------|-----------------|
| Overall | 85% | 70% (`--cov-fail-under=70`) |
| Business logic | 90% | reported, not gated |

Business logic paths: `src/voxforge/modules/`, `src/voxforge/core/`

Worker entrypoints omitted from coverage run (see `pyproject.toml`):

- `infrastructure/livekit/worker.py`
- `infrastructure/knowledge/worker.py`

## Generate reports

```bash
make test-cov
```

Outputs:

| Artifact | Format |
|----------|--------|
| `coverage.xml` | Cobertura / CI |
| `htmlcov/index.html` | Interactive HTML |
| `docs/testing/coverage-report.md` | Summary table |

## CI

The `lint-and-test` job uploads all three as the `coverage-reports` artifact.

## Ratchet plan

1. **70%** — current gate (this sprint)
2. **75%** — after voice WebSocket + pipeline tests expanded
3. **85%** — production deployment target

## High-gap modules (prioritize next)

- `api/ws/voice.py`
- `modules/voice_gateway/application/pipeline.py`
- `modules/auth/application/sso_service.py`
- `infrastructure/tools/mcp_stdio_client.py`

See `coverage-report.md` after each CI run for current numbers.
