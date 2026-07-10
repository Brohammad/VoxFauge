#!/usr/bin/env bash
# End-to-end: create DO droplet → DNS (optional) → SSH deploy.
#
# 1. cp .env.deploy.example .env.deploy
# 2. Add TOKEN=dop_v1_... (and optional CF_API_TOKEN + CF_ZONE_ID)
# 3. ./scripts/deploy-all.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.deploy ]]; then
  echo "Create .env.deploy first:" >&2
  echo "  cp .env.deploy.example .env.deploy" >&2
  echo "  # add TOKEN=dop_v1_... from cloud.digitalocean.com/account/api/tokens" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env.deploy
set +a

if [[ -f deploy/.droplet-ip ]]; then
  DROPLET_IP=$(cat deploy/.droplet-ip)
  echo "Using existing droplet IP: $DROPLET_IP"
else
  ./scripts/create-droplet.sh
  DROPLET_IP=$(cat deploy/.droplet-ip)
fi

if [[ -n "${CF_API_TOKEN:-}" && -n "${CF_ZONE_ID:-}" ]]; then
  export DROPLET_IP
  ./scripts/cloudflare-dns.sh || echo "DNS update failed — set A record manually in Cloudflare"
  sleep 15
else
  echo ""
  echo "Add Cloudflare A record (grey cloud): voxforge.brohammad.tech → $DROPLET_IP"
  echo "Press Enter when done..."
  read -r
fi

export DROPLET_IP
./scripts/remote-deploy.sh
