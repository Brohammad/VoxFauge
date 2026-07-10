# Backup & Restore Guide

## Create backup

```bash
cd /opt/VoxForge
./deploy.sh backup
```

Backups are written to the `postgres_backups` Docker volume.

## Schedule automated backups

```bash
./scripts/install-backup-cron.sh
```

Default: daily at 03:00 UTC.

## List backups

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  ls -la /backups/
```

## Restore from backup

```bash
# Stop app to prevent writes
docker compose -f docker-compose.prod.yml stop app knowledge-worker livekit-worker

# Restore (replace BACKUP_FILE)
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_restore -U voxforge -d voxforge --clean --if-exists < /backups/BACKUP_FILE

# Restart
./deploy.sh up
```

## Restore validation checklist

- [ ] `/api/v1/ready` returns ok
- [ ] Dashboard login works
- [ ] Recent sessions visible
- [ ] Knowledge documents present (if used)
- [ ] Handoff queue state correct

## Off-site backup

Copy backup files to S3, Backblaze, or encrypted storage:

```bash
docker compose -f docker-compose.prod.yml cp postgres:/backups/latest.dump ./latest.dump
# Upload with your tool of choice
```

Never store `.env.production` in the same bucket without encryption.
