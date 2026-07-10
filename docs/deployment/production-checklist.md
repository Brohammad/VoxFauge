# Production Launch Checklist

Use this checklist before announcing the public URL.

## Infrastructure

- [ ] VPS provisioned (2 vCPU, 4 GB RAM minimum)
- [ ] Domain DNS A record points to VPS IP
- [ ] Ports 80 and 443 open
- [ ] Docker and Docker Compose installed
- [ ] `.env.production` created from `.env.production.example`
- [ ] `POSTGRES_PASSWORD` set (strong, unique)
- [ ] `JWT_SECRET_KEY` set (`openssl rand -hex 32`)
- [ ] `API_KEY_HASH_PEPPER` set (`openssl rand -hex 32`)
- [ ] `PUBLIC_BASE_URL`, `TRUSTED_HOSTS`, `CORS_ORIGINS` match domain
- [ ] `ENV_FILE=.env.production APP_ENV=production python scripts/validate_production_env.py` passes

## Deploy

- [ ] `./deploy.sh init` completed without errors
- [ ] TLS certificate issued (HTTPS loads without warnings)
- [ ] `./deploy.sh status` shows healthy services
- [ ] `GET /api/v1/health` returns 200
- [ ] `GET /api/v1/ready` shows database and redis ok
- [ ] `./scripts/smoke-test.sh` passes (set `BASE_URL`)

## Public demo

- [ ] `GET /` landing page loads
- [ ] `GET /demo` loads
- [ ] `POST /api/v1/demo/quickstart` completes in under 60 seconds
- [ ] Demo credentials work on `/dashboard` login
- [ ] Rate limiting returns 429 after threshold (optional smoke test)

## Security

- [ ] `.env.production` not in git
- [ ] `/api/v1/metrics` returns 403 via NGINX
- [ ] HTTP redirects to HTTPS
- [ ] HSTS header present
- [ ] Demo org contains no customer data

## Operations

- [ ] Backup cron scheduled (`./deploy.sh backup`)
- [ ] Log rotation configured (compose `logging` options)
- [ ] Resource limits reviewed in `docker-compose.prod.yml`
- [ ] Certbot renewal sidecar running

## Documentation

- [ ] [Deployment guide](guide.md) reviewed
- [ ] [Operations guide](operations.md) accessible to on-call
- [ ] [Troubleshooting](troubleshooting.md) bookmarked

## Optional (LiveKit WebRTC)

- [ ] LiveKit Cloud project configured
- [ ] `LIVEKIT_*` env vars set
- [ ] `livekit-worker` running (auto-started by `./deploy.sh init` when `LIVEKIT_URL` set)
- [ ] `/examples/livekit` connects and receives agent audio

## Optional (Monitoring)

- [ ] `METRICS_BEARER_TOKEN` set in `.env.production`
- [ ] Prometheus + Grafana running (auto-started by deploy)
- [ ] Grafana accessible via SSH tunnel to `127.0.0.1:3000`

## Post-launch (next phase — not Phase 5)

- [ ] Load testing
- [ ] Performance optimization
- [ ] WAF / DDoS protection
- [ ] Managed database migration
- [ ] Secret manager integration
