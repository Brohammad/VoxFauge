# Production Runbook

Day-2 operations for VoxForge at https://voxforge.brohammad.tech.

## Quick reference

| Action | Command |
|--------|---------|
| Status | `./deploy.sh status` |
| Logs | `./deploy.sh logs` or `docker compose -f docker-compose.prod.yml logs -f app` |
| Restart app | `docker compose -f docker-compose.prod.yml restart app` |
| Full redeploy | `./deploy.sh up` |
| Backup DB | `./deploy.sh backup` |
| Renew TLS | `./deploy.sh renew-cert` |
| Smoke test | `BASE_URL=https://voxforge.brohammad.tech ./scripts/smoke-test.sh` |

## Health endpoints

| Endpoint | Expected | Action if fail |
|----------|----------|----------------|
| `/api/v1/health` | `{"status":"ok"}` | Check app container logs |
| `/api/v1/ready` | database + redis ok | Check postgres/redis containers |
| `/` | 200 HTML | Check nginx + app routing |
| `/demo` | 200 HTML | Verify `DEMO_ENABLED=true` |

## Service dependencies

```
postgres, redis → app (healthy) → nginx
                → optional: livekit-worker, knowledge-worker, prometheus, grafana
```

## Common incidents

### App unhealthy

1. `docker compose -f docker-compose.prod.yml logs app --tail=100`
2. Check `DATABASE_URL`, `REDIS_URL` in `.env.production`
3. `docker compose -f docker-compose.prod.yml restart app`

### TLS certificate expiring

Certbot sidecar renews every 12h. Manual: `./deploy.sh renew-cert`

### High latency

1. Check provider API status (OpenAI, Deepgram, etc.)
2. Review `/api/v1/dashboard/latency` in operator dashboard
3. Consider scaling VPS or enabling caching

### Disk full

1. `docker system prune -f` (careful in production)
2. Rotate logs: `truncate -s 0` on large log files
3. Verify backup retention policy

## Escalation

| Severity | Response time | Action |
|----------|---------------|--------|
| P0 — site down | 15 min | Restart stack, check DNS/TLS |
| P1 — degraded | 1 hr | Partial outage, failover providers |
| P2 — minor | Next business day | Non-blocking issues |

## Related

- [Incident response](incident-response.md)
- [Disaster recovery](disaster-recovery.md)
- [Rollback guide](../deployment/rollback-guide.md)
