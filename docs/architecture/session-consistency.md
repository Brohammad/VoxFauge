# Session Consistency (Postgres + Redis)

P1 hardening: PostgreSQL is the **source of truth**; Redis holds ephemeral streaming state (phase, sequence, interrupt, heartbeats, tool-failure counters).

## Design

```
create_session:
  1. INSERT voice_sessions (Postgres)     ← authoritative
  2. WRITE session:{id}:state (Redis)
  3. On Redis failure → mark session FAILED in Postgres, raise SessionStateError

end_session:
  1. UPDATE voice_sessions → completed (Postgres)   ← authoritative
  2. DELETE Redis keys (best-effort)
  3. On Redis delete failure → log + metric; operation still succeeds
  4. Idempotent if already completed/failed

resume / activate / handoff:
  If Redis state missing → reconcile from Postgres metadata + status
```

No distributed transactions. Compensating actions and reconciliation replace two-phase commit.

## Reconciliation

`SessionManager.ensure_ephemeral_state()` rebuilds Redis from:

- `voice_sessions.status` → `SessionPhase`
- `voice_sessions.metadata_` → `SessionState.config`
- TTL from `session_state_ttl_seconds` or `handoff_session_ttl_seconds`

Triggered automatically on `resume_session`, `activate_session` (if needed), and handoff state transitions.

## Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Postgres first on create | No orphan Redis without DB row | Create fails entirely if Redis down |
| Best-effort Redis delete on end | Session always ends in DB | Stale Redis keys until TTL expiry |
| Reconcile on resume | Survives Redis flush/restart | Rebuilt state loses in-flight sequence/interrupt unless client sends `last_sequence` |
| FAILED status on create compensation | Clear audit trail | Client must create a new session |

## Observability

| Signal | Meaning |
|--------|---------|
| `voxforge_session_consistency_total{operation="create",outcome="compensated"}` | Redis failed during create; session marked FAILED |
| `voxforge_session_consistency_total{operation="end",outcome="redis_cleanup_failed"}` | DB ended; Redis delete failed |
| `voxforge_session_consistency_total{operation="reconcile",outcome="success"}` | Redis rebuilt from Postgres |
| `session_ephemeral_reconciled` log | Reconciliation event |
| `session.reconcile_ephemeral` trace span | OTel span on reconcile |

## Related

- [failure-recovery.md](./failure-recovery.md) — operational failure scenarios
- [voice-pipeline.md](./voice-pipeline.md) — session lifecycle in the voice stack
