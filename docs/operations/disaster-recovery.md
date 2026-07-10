# Disaster Recovery

## RPO / RTO assumptions (single-node VPS)

| Metric | Target | Notes |
|--------|--------|-------|
| **RPO** (max data loss) | 24 hours | Daily Postgres backups |
| **RTO** (time to restore) | 2–4 hours | Fresh VPS + restore |

## Backup strategy

| Asset | Method | Frequency | Retention |
|-------|--------|-----------|-----------|
| PostgreSQL | `deploy.sh backup` → `scripts/backup_postgres.sh` | Daily (cron) | 7 days local |
| `.env.production` | Encrypted off-site copy | On change | Indefinite |
| TLS certs | Certbot volume `certbot_certs` | Auto-renew | N/A |
| Application code | Git (`origin/main`) | Every release | Git history |

## Restore procedure

### 1. Provision replacement VPS

```bash
# On new Ubuntu 24.04 host
./scripts/bootstrap-server.sh
git clone https://github.com/Brohammad/VoxForge.git /opt/VoxForge
```

### 2. Restore environment

Copy `.env.production` from secure backup (do not commit secrets).

```bash
./scripts/setup-production-env.sh voxforge.brohammad.tech
# Merge saved secrets into .env.production
```

### 3. Restore database

```bash
./deploy.sh init  # starts postgres
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U voxforge -d voxforge --clean < backup.dump
```

### 4. Verify

```bash
./deploy.sh up
BASE_URL=https://voxforge.brohammad.tech ./scripts/smoke-test.sh
```

## DNS failover

Update A record for `voxforge.brohammad.tech` to new VPS IP via Cloudflare or registrar.

## Validate restores quarterly

- [ ] Restore backup to staging VPS
- [ ] Run smoke test + manual QA
- [ ] Document duration and issues

See also [backup-restore.md](backup-restore.md).
