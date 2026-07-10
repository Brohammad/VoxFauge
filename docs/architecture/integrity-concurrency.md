# Integrity & Concurrency (P1 Group 2)

P1 hardening: deterministic behavior under concurrent requests via database constraints, idempotent application logic, and `IntegrityError` recovery.

**Related:** [session-consistency.md](./session-consistency.md), [failure-recovery.md](./failure-recovery.md)

---

## Concurrency model

```
Request A ──┐
            ├──► Application check (optional fast path)
Request B ──┘         │
                      ▼
              PostgreSQL unique constraint
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     INSERT wins              INSERT loses
          │                       │
          ▼                       ▼
   Continue workflow      Catch IntegrityError
                          Re-fetch existing row
                          Return idempotent result
```

No distributed locks. Postgres `UNIQUE` indexes are the enforcement layer; application code converts violations into domain outcomes.

---

## Idempotency guarantees

| Resource | Constraint | Behavior on duplicate |
|----------|------------|----------------------|
| Handoff per session | `uq_handoff_records_session` | Return existing `HandoffPackage`; no second ticket/snapshot |
| Outcome KPI per session | `uq_outcome_kpis_session` | Upsert updates same row; metrics distinguish create vs update |
| KB document version | `uq_knowledge_document_versions_doc_ver` | Return existing version row |
| KB chunk per version index | `uq_knowledge_chunks_version_index` | Skip duplicate insert |
| Handoff snapshot | `uq_conversation_snapshots_handoff` | Return existing snapshot |
| Support ticket (mock) | `session_id` idempotency key | Return existing ticket for same session |

### Handoff state machine guards

| Transition | Allowed from | Idempotent when |
|------------|--------------|-----------------|
| Accept | `pending`, `assigned` | Already `active` for same agent |
| Complete | `pending`, `assigned`, `active` | Already `completed` |
| Cancel | `pending`, `assigned`, `active` | Already `cancelled` |

Concurrent accept/complete/cancel uses conditional `UPDATE … WHERE status IN (…)` — last invalid transition returns `409 Conflict`.

### Session lifecycle

| Operation | Guard |
|-----------|-------|
| `activate_session` | Idempotent if already `active`; rejects terminal |
| `resume_session` | Rejects terminal sessions before reconcile |
| `end_session` | Idempotent if already `completed`/`failed` (P1 Group 1) |

### Replay token

Single `ReplayLinkService.generate()` call per handoff — ticket and DB store the same token.

---

## Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Unique constraints over app locks | Survives multi-instance API | Requires migration for new constraints |
| `begin_nested()` savepoints | Partial rollback on conflict without aborting whole request | Slight overhead per guarded insert |
| Check-then-act fast path | Avoids DB round-trip on retries | Race still possible; constraint is authoritative |
| One handoff per session (forever) | Simple idempotency | No re-escalation after cancel/complete without schema change |
| Mock ticket idempotency by `session_id` | Prevents duplicate tickets in dev/demo | Production providers need provider-native idempotency keys (P2) |

---

## Observability

| Metric | Meaning |
|--------|---------|
| `voxforge_integrity_violations_total{resource,operation}` | Unique constraint hit, recovered idempotently |
| `voxforge_duplicate_suppressed_total{resource}` | Duplicate business operation returned existing resource |
| `voxforge_outcome_updates_total{intent}` | Outcome KPI update (not first insert) |
| `voxforge_session_consistency_total{operation="activate",outcome="idempotent"}` | Redundant activate suppressed |

Structured logs: `handoff_create_duplicate_suppressed`, `outcome_upsert_duplicate_suppressed`, `knowledge_version_duplicate_suppressed`.

---

## Error handling

Raw `IntegrityError` is never exposed to clients. API maps:

- `404` — resource not found
- `409` — invalid state transition or conflict (e.g. accept after complete)

---

## Tests

- `tests/unit/test_integrity_hardening.py` — duplicate inserts, upserts, guards, ticket idempotency
- `tests/unit/test_session_consistency.py` — session lifecycle (P1 Group 1)
- `tests/integration/test_handoff.py` — sequential handoff idempotency

Concurrent integration tests can extend `test_handoff_idempotent_per_session` with `asyncio.gather` against the HTTP API.
