#!/usr/bin/env bash
# Daily PostgreSQL backup — schedule via cron on the host.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/deploy/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/voxforge_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

source "${ENV_FILE:-$ROOT/.env.production}"

POSTGRES_USER="${POSTGRES_USER:-voxforge}"
POSTGRES_DB="${POSTGRES_DB:-voxforge}"

echo "Writing backup to $FILE"
docker compose -f "$ROOT/docker-compose.prod.yml" exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"

find "$BACKUP_DIR" -name 'voxforge_*.sql.gz' -mtime +14 -delete
echo "Backup complete."
