# VoxForge Operations Guide

Day-two operations for a Docker Compose production deployment.

## Service topology

```
Internet → NGINX (:443) → app (:8000) → postgres / redis
                      ↘ livekit-worker (optional profile)
Certbot → renews TLS certificates (12h loop)
```

## Health monitoring

| Endpoint | Type | Expected |
|----------|------|----------|
| `GET /api/v1/health` | Liveness | `{"status":"ok"}` |
| `GET /api/v1/ready` | Readiness | `database: ok`, `redis: ok` |

Check from the host:

```bash
./deploy.sh status
curl -fsS https://your-domain.example/api/v1/ready
```

Docker healthchecks run inside the `app` container every 30s.

## Logs

All services use JSON-file logging with rotation:

| Service | max-size | max-file |
|---------|----------|----------|
| app | 20m | 5 |
| postgres | 10m | 3 |
| redis | 10m | 3 |
| nginx | 10m | 3 |

View logs:

```bash
./deploy.sh logs
docker compose -f docker-compose.prod.yml logs app --tail=200
```

## Backups

Manual backup:

```bash
./deploy.sh backup
```

Backups land in `deploy/backups/voxforge_<timestamp>.sql.gz`.

Restore (maintenance window required):

```bash
docker compose -f docker-compose.prod.yml stop app livekit-worker
gunzip -c deploy/backups/voxforge_YYYYMMDDTHHMMSSZ.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U voxforge voxforge
docker compose -f docker-compose.prod.yml start app
```

## Deploying updates

```bash
git pull
./deploy.sh up
```

Migrations run automatically via `docker-entrypoint.sh` before the API starts.

## TLS renewal

Certbot runs in a sidecar with automatic renewal every 12 hours. To force renewal:

```bash
./deploy.sh renew-cert
```

Certificates are stored in the `certbot_certs` Docker volume.

## Scaling notes

This deployment targets a single-node VPS. Horizontal scaling is not supported in this compose profile. For higher load:

1. Move Postgres to managed database (Neon, RDS)
2. Move Redis to managed cache (ElastiCache, Upstash)
3. Run multiple `app` replicas behind a load balancer (future phase)

Current production runs `--workers 1` uvicorn. Increase only after load testing.

## Secret rotation

| Secret | Rotation procedure |
|--------|-------------------|
| `JWT_SECRET_KEY` | Update `.env.production`, restart app — invalidates existing tokens |
| `API_KEY_HASH_PEPPER` | Update env, restart — existing API keys must be re-issued |
| `POSTGRES_PASSWORD` | Update env + Postgres role, restart stack |
| TLS certs | Automatic via Certbot |

Never commit `.env.production` to version control.

## Observability

- Structured JSON logs via structlog
- Prometheus metrics at `/api/v1/metrics` (blocked at NGINX in production)
- OpenTelemetry export via `OTEL_EXPORTER_OTLP_ENDPOINT` (optional)

For metrics access in production, use SSH tunnel:

```bash
ssh -L 9090:localhost:8000 user@vps
curl localhost:9090/api/v1/metrics
```

## Incident response

1. Check `./deploy.sh status`
2. Review `app` logs for errors
3. Verify `/api/v1/ready` — isolates DB vs Redis failures
4. See [troubleshooting.md](troubleshooting.md)
