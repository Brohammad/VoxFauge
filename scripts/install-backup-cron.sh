#!/usr/bin/env bash
# Install daily Postgres backup cron on the VPS.
# Usage: ./scripts/install-backup-cron.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRON_LINE="0 3 * * * cd $ROOT && ./deploy.sh backup >> /var/log/voxforge-backup.log 2>&1"

if crontab -l 2>/dev/null | grep -qF "deploy.sh backup"; then
  echo "Backup cron already installed."
  exit 0
fi

( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
echo "Installed backup cron: $CRON_LINE"
