# Rate Limiting & Abuse Protection (P1 Group 3)

Redis-backed, category-driven rate limiting for all `/api/v1` routes. Protects compute, LLM usage, voice sessions, storage, replay, and knowledge operations.

**Related:** [failure-recovery.md](./failure-recovery.md), [operations.md](../deployment/operations.md)

---

## Architecture

```
HTTP request
    │
    ▼
RateLimitMiddleware ──► IP sustained + burst (all /api/v1 except exempt)
    │
    ▼
Route handler + auth
    │
    ▼
rate_limit_category dependency ──► org / session / user / api_key limits
```

WebSocket (`/api/v1/ws/voice`):
1. IP limit at connect (before `accept`)
2. Org limit on `start` / resume after authentication

**Implementation:** `src/voxforge/infrastructure/http/rate_limit.py`

---

## Endpoint Coverage Matrix

| Category | Routes | IP sustained / burst | Org limits | Fail mode |
|----------|--------|----------------------|------------|-----------|
| `auth_login` | POST login, register, refresh | 20/min · 5/10s | — | **closed** |
| `auth` | Other `/auth` | 40/min · 10/10s | — | **closed** |
| `demo` | `/demo` | 10/min · 3/10s | — | **closed** |
| `api_keys` | POST `/api-keys` | 10/min · 3/10s | 20/min | **closed** |
| `sessions_create` | POST `/sessions` | 30/min · 5/10s | 100/min | **closed** |
| `voice_ws` | WS `/ws/voice` | 20/min · 5/10s | 60/min | **closed** |
| `livekit` | POST token | 30/min · 5/10s | 80/min · session 20/min | **closed** |
| `knowledge_upload` | POST documents | 10/min · 2/10s | 30/min | **closed** |
| `knowledge_reindex` | POST reindex | 5/min · 2/10s | 20/min | **closed** |
| `knowledge_search` | POST search | 60/min · 15/10s | 200/min | open |
| `knowledge_collections` | POST collections | 20/min · 5/10s | 50/min | **closed** |
| `memory_search` | POST memory search | 60/min · 15/10s | 200/min | open |
| `replay` | GET replay | 30/min · 10/10s | 100/min · session 15/min | **closed** |
| `onboarding_sample` | POST run-sample-call | 5/min · 2/10s | 15/min | **closed** |
| `onboarding` | Other onboarding | 30/min · 8/10s | 60/min | **closed** |
| `dashboard` | GET dashboard | 120/min · 30/10s | 300/min | open |
| `sessions` | Other session routes | 120/min · 30/10s | 300/min · session 60/min | open |
| `api_default` | Remaining `/api/v1` | 120/min · 30/10s | 500/min | open |

**Exempt (no rate limit):** `/health`, `/ready`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`

---

## Redis Failure Matrix

| Category type | Redis down behavior | Rationale |
|---------------|---------------------|-----------|
| Auth, demo, sessions, voice, KB writes, replay, onboarding, API keys | **Fail closed** (503) | Prevent credential stuffing, session spam, cost abuse when guard is down |
| Knowledge search, memory search, dashboard, general API | **Fail open** | Authenticated ops; availability over strict throttling during Redis blip |

Configure via `RATE_LIMIT_FAIL_CLOSED_CATEGORIES` (comma-separated category names).

---

## Configuration

| Setting | Default | Purpose |
|---------|---------|---------|
| `RATE_LIMIT_ENABLED` | `true` | Master switch |
| `RATE_LIMIT_MULTIPLIER` | `1.0` | Scale all limits (e.g. `0.5` in staging) |
| `RATE_LIMIT_FAIL_CLOSED_CATEGORIES` | see `config.py` | Categories that return 503 when Redis unavailable |

Legacy `RATE_LIMIT_PATHS` / `RATE_LIMIT_PER_MINUTE` are deprecated; middleware uses category policies.

---

## Cost Protection Strategy

| Expensive operation | Protection |
|--------------------|------------|
| LLM / voice turns | Session create + WS connect + org limits |
| Embeddings | KB upload, search, memory search org caps |
| Knowledge ingestion | Upload + reindex strict IP/org limits |
| Replay | IP + org + per-session limits |
| Onboarding sample call | Very low sustained/burst (5/min, 2/10s) |
| Dashboard aggregates | Org cap prevents query storms |

---

## Observability

| Metric | Labels |
|--------|--------|
| `voxforge_rate_limit_allowed_total` | `category`, `dimension` |
| `voxforge_rate_limit_blocked_total` | `category`, `dimension` |
| `voxforge_rate_limit_redis_errors_total` | `category`, `fail_mode` |

Logs: `rate_limit_exceeded`, `rate_limit_redis_error` (structured, includes category and dimension).

---

## Operational Tuning

1. **Shared NAT / corporate egress:** Raise org limits before IP limits; consider API keys for server-to-server.
2. **Redis outage:** Fail-closed categories return 503 — monitor `rate_limit_redis_errors_total` and `/ready`.
3. **Pilot load test:** Set `RATE_LIMIT_MULTIPLIER=2.0` temporarily if legitimate traffic hits 429s.
4. **NGINX edge:** Production HTTPS still applies `limit_req` on auth/demo; app layer is defense in depth.

---

## Trade-offs

| Choice | Benefit | Cost |
|--------|---------|------|
| Single middleware + route dependencies | No duplicate engines | Org limits require auth (not on anonymous replay token path beyond IP) |
| Per-category fail mode | Security where it matters; uptime for read-heavy dashboard | Operators must understand two behaviors |
| Fixed 60s / 10s windows | Simple Redis INCR; no token bucket state | Less smooth than sliding window |
| IP from `X-Forwarded-For` | Works behind NGINX | Spoofable if app exposed without trusted proxy |
