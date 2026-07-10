# End-to-End Tests

E2E tests in `tests/e2e/` simulate production-like paths using the in-process ASGI test client and mock providers.

## Scenarios

| Test | Path |
|------|------|
| Deployment smoke | `test_deployment_smoke.py` |
| Health / ready / metrics | `test_deployment_smoke.py` |
| Register → sample call → replay → dashboard | `test_deployment_smoke.py` |

WebSocket lifecycle is covered in `tests/feature/test_session_lifecycle_flow.py` and `tests/integration/test_voice_pipeline_e2e.py`.

LiveKit, full audio STT streaming, and docker-compose orchestration smoke are candidates for a nightly job (not in default PR CI).

## Run

```bash
make test-e2e
```

## Production validation

Against a running deployment:

```bash
docker compose -f docker-compose.prod.yml up -d
scripts/e2e_qa_manual.py
```

Live stack test (requires API keys in `.env`):

```bash
scripts/run_live_tests.sh
```
