#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu 24.04 VPS for VoxForge production deploy.
# Run as root: curl -fsSL ... | bash   OR   ./scripts/bootstrap-server.sh

set -euo pipefail

log() { printf '==> %s\n' "$*"; }

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root (e.g. ssh root@your-vps ./bootstrap-server.sh)" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

log "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

log "Installing git, curl, ufw..."
apt-get install -y -qq git ufw curl ca-certificates

if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
fi

log "Configuring firewall..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

log "Bootstrap complete."
log "Next: clone repo, then run ./deploy.sh init (creates .env.production automatically if missing)"
