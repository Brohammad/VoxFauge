# VoxForge Troubleshooting

Common production issues and resolutions.

## Container won't start — production validation failed

**Symptom:** `app` exits immediately with configuration errors.

**Cause:** `validate_production_settings()` or `validate_production_env.py` rejected weak secrets.

**Fix:**

```bash
ENV_FILE=.env.production APP_ENV=production python scripts/validate_production_env.py
```

Ensure `JWT_SECRET_KEY` and `API_KEY_HASH_PEPPER` are at least 32 characters and do not contain `change-me`. Set `TRUSTED_HOSTS` to your domain.

---

## 502 Bad Gateway from NGINX

**Symptom:** HTTPS works but pages return 502.

**Causes:**

1. `app` container not running
2. Migrations still running
3. App crashed during startup

**Fix:**

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs app --tail=100
```

Wait for migrations to complete. Check `/api/v1/health` inside the container:

```bash
docker compose -f docker-compose.prod.yml exec app curl -fsS http://127.0.0.1:8000/api/v1/health
```

---

## TLS certificate errors

**Symptom:** Browser shows certificate warning or HTTPS unavailable.

**Causes:**

1. DNS not pointing to server during `init`
2. Port 80 blocked
3. Certbot challenge failed

**Fix:**

```bash
# Verify DNS
dig +short your-domain.example

# Re-run certificate request
rm deploy/nginx/certs-ready
./deploy.sh init
```

Ensure `/.well-known/acme-challenge/` is reachable on port 80.

---

## Demo returns 404

**Symptom:** `/demo` page loads but API returns `Demo is not enabled`.

**Fix:** Set in `.env.production`:

```env
DEMO_ENABLED=true
```

Restart: `./deploy.sh up`

---

## Demo quickstart fails

**Symptom:** `POST /api/v1/demo/quickstart` returns 500.

**Causes:**

1. Migration 009 not applied (demo org missing)
2. Redis unavailable
3. Mock provider misconfiguration

**Fix:**

```bash
docker compose -f docker-compose.prod.yml exec app alembic current
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
docker compose -f docker-compose.prod.yml exec app python scripts/ensure_demo_account.py
```

---

## Rate limit 429

**Symptom:** `Rate limit exceeded` on `/api/v1/demo` or `/api/v1/auth`.

**Cause:** `RATE_LIMIT_PER_MINUTE` exceeded per client IP.

**Fix:** Wait 60 seconds or adjust `RATE_LIMIT_PER_MINUTE` in `.env.production`. Behind NGINX, rate limiting uses `X-Forwarded-For`.

---

## Database connection errors

**Symptom:** `/api/v1/ready` shows `database: error`.

**Fix:**

```bash
docker compose -f docker-compose.prod.yml ps postgres
docker compose -f docker-compose.prod.yml logs postgres --tail=50
```

Verify `POSTGRES_PASSWORD` matches between `.env.production` and the running volume. If password was changed after first deploy, reset the volume (data loss) or alter the Postgres role manually.

---

## WebSocket disconnects

**Symptom:** Voice sessions drop after ~60s.

**Cause:** NGINX proxy timeout too low.

**Fix:** Production NGINX template sets `proxy_read_timeout 3600s` for `/api/v1/ws/`. Verify `deploy/nginx/conf.d/voxforge.conf` includes the WebSocket block and reload NGINX.

---

## LiveKit worker not joining rooms

**Symptom:** WebRTC clients connect but no agent audio.

**Checklist:**

1. `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` set
2. Worker running: `docker compose --profile livekit ps`
3. `LIVEKIT_DISPATCH_ENABLED=true`
4. Worker logs: `docker compose --profile livekit logs livekit-worker`

---

## High memory usage

**Symptom:** OOM kills or slow responses.

**Check:**

```bash
docker stats --no-stream
```

Resource limits are in `docker-compose.prod.yml`. Increase VPS RAM or lower `MEMORY_ENABLED` / `MCP_STARTUP_DISCOVER` if running demo-only.

---

## Getting help

1. Collect `./deploy.sh status` output
2. Export last 200 lines of `app` logs
3. Note `APP_ENV`, provider settings (redact API keys)
4. Check [operations.md](operations.md) and [security.md](security.md)
