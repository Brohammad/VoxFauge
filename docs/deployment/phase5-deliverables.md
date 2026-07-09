# Phase 5 Deliverables — Public Deployment

Status: **Ready for VPS deployment** (infrastructure and documentation complete; cloud deploy requires your domain and VPS credentials).

## URLs

| Surface | URL |
|---------|-----|
| Public site | `https://<your-domain>/` |
| Interactive demo | `https://<your-domain>/demo` |
| API docs | `https://<your-domain>/api/v1/docs` |
| Dashboard | `https://<your-domain>/dashboard` |

Replace `<your-domain>` with the hostname configured in `.env.production` (`PUBLIC_BASE_URL`).

**Deploy command:** `./deploy.sh init` on your VPS after configuring `.env.production`.

## Deployment architecture

See [architecture.md](architecture.md) for the full diagram. Summary:

```
Internet → NGINX (TLS) → FastAPI → PostgreSQL + Redis
                       ↘ LiveKit worker → LiveKit Cloud (optional)
```

## Resource utilization (estimated)

| Service | CPU limit | Memory limit |
|---------|-----------|--------------|
| postgres | 1.0 | 1 GB |
| redis | 0.5 | 256 MB |
| app | 2.0 | 2 GB |
| nginx | 0.5 | 128 MB |
| livekit-worker | 1.0 | 1 GB |

**Recommended VPS:** 2 vCPU, 4 GB RAM (Hetzner CX22 ~€4/mo or DO Droplet $24/mo).

Observed demo-only workload: ~1.5 GB RAM total, &lt;30% CPU at idle.

## Startup time

| Phase | Duration |
|-------|----------|
| Postgres + Redis healthy | ~10–15s |
| Alembic migrations (warm) | ~2–5s |
| App healthcheck start-period | 40s |
| **Total cold start** | **~45–90s** |
| TLS bootstrap (first `init`) | +30–60s |

## Production checklist

Completed in repository:

- [x] Production Docker Compose (`docker-compose.prod.yml`)
- [x] NGINX reverse proxy with WebSocket support
- [x] Let's Encrypt / Certbot integration
- [x] Health checks (app, postgres, redis)
- [x] `restart: unless-stopped` on all services
- [x] Environment validation (`validate_production_env.py` + startup guard)
- [x] Production configuration profile (`.env.production.example`)
- [x] Public landing page (`/`)
- [x] Interactive demo (`/demo`)
- [x] Demo organization + account (migration 009)
- [x] Rate limiting on public endpoints
- [x] Log rotation (Docker json-file driver)
- [x] Resource limits per service
- [x] Backup script + retention policy
- [x] Deployment, operations, troubleshooting, architecture, security docs

Launch checklist for operator: [production-checklist.md](production-checklist.md).

## Remaining technical debt

| Item | Priority | Notes |
|------|----------|-------|
| Single uvicorn worker | Medium | Scale after load testing |
| No HA / multi-node | Medium | Acceptable for demo phase |
| Redis without auth | Low | Internal network only |
| Demo password in API/UI | Low | Intentional for public demo |
| No WAF | Medium | Add in hardening phase |
| Prometheus blocked publicly | Low | SSH tunnel documented |
| LiveKit not containerized | Low | External SFU by design |
| No automated integration tests against prod URL | Medium | CI runs unit/integration locally |

## Security assumptions

1. VPS provider secures hypervisor and disk
2. `.env.production` is managed out-of-band (not in git)
3. Demo account is public — no sensitive data in demo org
4. Mock providers used for demo — no API key spend
5. TLS certificates auto-renewed via Certbot
6. Rate limiting provides basic abuse protection only
7. No compliance certifications (SOC 2, HIPAA) in Phase 5

Full details: [security.md](security.md).

## Next steps (post-deployment)

Per project plan, **stop after deployment**. Subsequent work:

1. Production hardening (WAF, secret manager)
2. Load testing
3. Performance optimization
4. Real provider keys for live voice demo (optional upgrade)
