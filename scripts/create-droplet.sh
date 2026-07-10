#!/usr/bin/env bash
# Create the VoxForge DigitalOcean droplet ($12/mo, 2GB, NYC1).
#
#   export TOKEN=dop_v1_...   # or DO_API_TOKEN
#   ./scripts/create-droplet.sh
#
# Prints public IP when ready. Then run:
#   DROPLET_IP=<ip> ./scripts/remote-deploy.sh

set -euo pipefail

TOKEN="${TOKEN:-${DO_API_TOKEN:-}}"
: "${TOKEN:?Set TOKEN or DO_API_TOKEN (DigitalOcean API token)}"

REGION="${REGION:-nyc1}"
SIZE="${SIZE:-s-1vcpu-2gb}"
IMAGE="${IMAGE:-ubuntu-24-04-x64}"
SSH_KEY_ID="${SSH_KEY_ID:-57694274}"
NAME="${NAME:-voxforge}"

log() { printf '==> %s\n' "$*"; }

log "Creating droplet: $NAME ($SIZE in $REGION)..."
resp=$(curl -fsS -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"name\": \"$NAME\",
    \"region\": \"$REGION\",
    \"size\": \"$SIZE\",
    \"image\": \"$IMAGE\",
    \"ssh_keys\": [$SSH_KEY_ID],
    \"backups\": false,
    \"ipv6\": false,
    \"monitoring\": true,
    \"tags\": [\"voxforge\"]
  }" \
  "https://api.digitalocean.com/v2/droplets")

DROPLET_ID=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['droplet']['id'])")
log "Droplet ID: $DROPLET_ID — waiting for public IP..."

for _ in $(seq 1 60); do
  ip=$(curl -fsS \
    -H "Authorization: Bearer $TOKEN" \
    "https://api.digitalocean.com/v2/droplets/$DROPLET_ID" \
    | python3 -c "
import sys, json
d = json.load(sys.stdin)['droplet']
for n in d.get('networks', {}).get('v4', []):
    if n.get('type') == 'public':
        print(n['ip_address'])
        break
")
  if [[ -n "$ip" ]]; then
    echo "$ip" > "$(dirname "$0")/../deploy/.droplet-ip"
    log "Droplet ready!"
    echo "  IP: $ip"
    echo "  SSH: ssh root@$ip"
    echo ""
    echo "DNS (Cloudflare, grey cloud): voxforge.brohammad.tech → $ip"
    echo ""
    echo "Deploy: DROPLET_IP=$ip ./scripts/remote-deploy.sh"
    exit 0
  fi
  sleep 5
done

die() { echo "ERROR: $*" >&2; exit 1; }
die "Timed out waiting for public IP (droplet $DROPLET_ID)"
