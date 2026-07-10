# Feature Tests

Feature tests live in `tests/feature/` and exercise realistic business flows with mock providers.

## Flows covered

### Customer support (`test_customer_support_flow.py`)

```
Session → Sample call → Handoff → Ticket → Accept → Replay → Dashboard → Complete
```

### Knowledge upload (`test_knowledge_upload_flow.py`)

```
Upload → Parse → Chunk → Embed → Store → Search → Citation
```

### Replay (`test_replay_flow.py`)

```
Conversation → Evaluation events → Replay timeline → Signed URL verify
```

### Session lifecycle (`test_session_lifecycle_flow.py`)

```
Create → Voice turns (sample call) → Replay → End (REST + WebSocket)
```

### Memory (`test_memory_flow.py`)

```
Store turn → Semantic search → Retrieved content
```

## Assertions

Feature tests verify:

- HTTP status codes and response shape
- Database-visible state (via API reads)
- Replay timeline event types
- Handoff idempotency and ticket creation

Metrics and tracing are covered in integration observability tests (`tests/integration/test_observability.py`).

## Run

```bash
make test-feature
# or
pytest tests/feature -m feature -v
```
