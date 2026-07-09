# VoxForge Deployment Guide

Deploy VoxForge on a single VPS using Docker Compose, NGINX, and Let's Encrypt TLS.

## Target environment

| Requirement | Recommendation |
|-------------|----------------|
| Provider | Hetzner CX22 or DigitalOcean Droplet (2 vCPU, 4 GB RAM) |
| OS | Ubuntu 24.04 LTS |
| Domain | A record pointing to VPS public IP |
| Ports | 80, 443 open inbound |

## Prerequisites

1. Docker Engine 24+ and Docker Compose v2
2. Domain DNS propagated to the server
3. Voice provider API keys (optional — mock providers work for the public demo)

## Quick deploy

```bash
# On the VPS
git clone https://github.com/your-org/VoxForge.git
cd VoxForge

cp .env.production.example .env.production
# Edit secrets: POSTGRES_PASSWORD, JWT_SECRET_KEY, API_KEY_HASH_PEPPER, PUBLIC_BASE_URL

chmod +x deploy.sh scripts/backup_postgres.sh
./deploy.sh init
```

`init` will:

1. Validate production environment variables
2. Render NGINX configuration for your domain
3. Start Postgres, Redis, and the API
4. Obtain a Let's Encrypt certificate via Certbot
5. Switch NGINX to HTTPS and start the renewal sidecar

## Environment configuration

Copy `.env.production.example` to `.env.production`. Required values:

| Variable | Description |
|----------|-------------|
| `PUBLIC_BASE_URL` | `https://your-domain.example` |
| `TRUSTED_HOSTS` | Same hostname (comma-separated if multiple) |
| `CORS_ORIGINS` | Same origin(s) as `PUBLIC_BASE_URL` |
| `POSTGRES_PASSWORD` | Strong database password |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `API_KEY_HASH_PEPPER` | `openssl rand -hex 32` |

For the public demo without paid API keys, keep:

```env
DEMO_ENABLED=true
STT_PROVIDER=mock
LLM_PROVIDER=mock
TTS_PROVIDER=mock
```

Validate before deploy:

```bash
ENV_FILE=.env.production APP_ENV=production python scripts/validate_production_env.py
```

## LiveKit (optional)

WebRTC transport requires an external LiveKit server (LiveKit Cloud recommended):

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

Start the worker:

```bash
docker compose -f docker-compose.prod.yml --profile livekit up -d livekit-worker
```

## Operations

| Command | Purpose |
|---------|---------|
| `./deploy.sh up` | Rebuild and start |
| `./deploy.sh down` | Stop stack |
| `./deploy.sh logs` | Tail service logs |
| `./deploy.sh backup` | PostgreSQL dump to `deploy/backups/` |
| `./deploy.sh renew-cert` | Force TLS renewal |
| `./deploy.sh status` | Health check summary |

### Scheduled backups

```cron
0 3 * * * cd /opt/VoxForge && ./deploy.sh backup >> /var/log/voxforge-backup.log 2>&1
```

Backups older than 14 days are pruned automatically.

## Public surfaces

After deploy:

| URL | Purpose |
|-----|---------|
| `/` | Landing page |
| `/demo` | Interactive voice pipeline demo |
| `/dashboard` | Operator dashboard |
| `/api/v1/docs` | OpenAPI reference |
| `/api/v1/health` | Liveness probe |
| `/api/v1/ready` | Readiness (DB + Redis) |

Demo credentials: `demo@voxforge.io` / `VoxForgeDemo!` (synced on container start when `DEMO_ENABLED=true`).

## Resource limits

Production compose sets per-service CPU and memory limits. See `docker-compose.prod.yml` for defaults. Adjust based on observed utilization (see [operations.md](operations.md)).

## Related docs

- [Operations guide](operations.md)
- [Troubleshooting](troubleshooting.md)
- [Architecture overview](architecture.md)
- [Security overview](security.md)
- [Production checklist](production-checklist.md)
