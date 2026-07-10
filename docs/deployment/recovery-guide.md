# Recovery Guide

Quick recovery procedures for common production failures.

## App won't start

```bash
docker compose -f docker-compose.prod.yml logs app --tail=200
python scripts/validate_production_env.py  # via deploy.sh validate_env
```

Common fixes:

- Regenerate secrets if `JWT_SECRET_KEY` too short
- Fix `DATABASE_URL` password mismatch with postgres container
- Ensure `PUBLIC_BASE_URL` matches actual domain

## NGINX 502 Bad Gateway

1. `docker compose -f docker-compose.prod.yml ps` — app must be healthy
2. Wait for `/api/v1/ready` before nginx routes traffic
3. `docker compose -f docker-compose.prod.yml restart app nginx`

## Certificate renewal failed

```bash
./deploy.sh renew-cert
# Check ACME webroot: deploy/nginx/conf.d/
# Ensure port 80 reachable for http-01 challenge
```

## Postgres connection errors

```bash
docker compose -f docker-compose.prod.yml restart postgres
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U voxforge
```

## Redis connection errors

```bash
docker compose -f docker-compose.prod.yml restart redis
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
```

## Complete stack reset (last resort)

```bash
./deploy.sh down
docker volume prune  # WARNING: destroys data without backup
./deploy.sh init
```

Only use volume prune on fresh installs — always backup first.

See [rollback-guide.md](rollback-guide.md) and [../operations/disaster-recovery.md](../operations/disaster-recovery.md).
