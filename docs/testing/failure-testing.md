# Failure Testing

Failure-mode tests in `tests/failure/` verify graceful degradation and recovery semantics.

## Scenarios

| Category | Tests |
|----------|-------|
| Infrastructure | Redis/DB unavailable → health/readiness status |
| Rate limiting | Fail-open for non-critical categories when Redis down |
| Auth | Invalid JWT, missing auth, API key scope violations |
| Replay tokens | Invalid/tampered token rejection |
| Concurrency | Parallel session create, concurrent handoff idempotency |
| Providers | Tool timeout, unknown tool, LLM timeout propagation |

## Not yet automated in CI

These require dedicated infrastructure fixtures or chaos tooling:

- Knowledge worker crash mid-job (manual: kill worker process)
- API/worker restart with in-flight sessions
- LiveKit reconnect
- MCP server offline (partial coverage in `tests/integration/test_mcp_discovery.py`)

## Run

```bash
make test-failure
```

## Expected behavior

- Critical dependencies down → `/ready` returns 503
- Optional components degraded → `/health` returns 200 with `degraded`
- Handoff and outcome writes remain idempotent under concurrent requests
