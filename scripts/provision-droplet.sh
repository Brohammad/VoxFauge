#!/usr/bin/env bash
# Provision a DigitalOcean Droplet for VoxForge (requires DO_API_TOKEN).
#
# Setup:
#   1. Redeem GitHub Student Pack → DigitalOcean $200 credit
#   2. Create API token: https://cloud.digitalocean.com/account/api/tokens
#   3. export DO_API_TOKEN=dop_v1_...
#   4. ./scripts/provision-droplet.sh
#
# Optional env:
#   DROPLET_NAME=voxforge
#   DROPLET_REGION=blr1
#   DROPLET_SIZE=s-2vcpu-4gb
#   SSH_KEY_ID=12345   (or script will use first account key)

set -euo pipefail

: "${DO_API_TOKEN:?Set DO_API_TOKEN (DigitalOcean API token)}"

DROPLET_NAME="${DROPLET_NAME:-voxforge}"
DROPLET_REGION="${DROPLET_REGION:-blr1}"
DROPLET_SIZE="${DROPLET_SIZE:-s-2vcpu-4gb}"
DROPLET_IMAGE="${DROPLET_IMAGE:-ubuntu-24-04-x64}"

api() {
  curl -fsS -X "$1" "https://api.digitalocean.com/v2$2" \
    -H "Authorization: Bearer $DO_API_TOKEN" \
    -H "Content-Type: application/json" \
    ${3:+ -d "$3"}
}

if [[ -z "${SSH_KEY_ID:-}" ]]; then
  SSH_KEY_ID=$(api GET "/account/keys" | python3 -c "import sys,json; keys=json.load(sys.stdin)['ssh_keys']; print(keys[0]['id'] if keys else '')")
  [[ -n "$SSH_KEY_ID" ]] || { echo "Add an SSH key to DigitalOcean or set SSH_KEY_ID"; exit 1; }
fi

echo "Creating Droplet: $DROPLET_NAME ($DROPLET_SIZE in $DROPLET_REGION)..."
payload=$(cat <<EOF
{
  "name": "$DROPLET_NAME",
  "region": "$DROPLET_REGION",
  "size": "$DROPLET_SIZE",
  "image": "$DROPLET_IMAGE",
  "ssh_keys": [$SSH_KEY_ID],
  "backups": false,
  "ipv6": false,
  "monitoring": true,
  "tags": ["voxforge"]
}
EOF
)

resp=$(api POST "/droplets" "$payload")
DROPLET_ID=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['droplet']['id'])")

echo "Droplet ID: $DROPLET_ID — waiting for public IP..."
for _ in $(seq 1 60); do
  ip=$(api GET "/droplets/$DROPLET_ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)['droplet']
nets = d.get('networks', {}).get('v4', [])
pub = [n['ip_address'] for n in nets if n['type']=='public']
print(pub[0] if pub else '')
" 2>/dev/null || true)
  if [[ -n "$ip" ]]; then
    echo ""
    echo "Droplet ready!"
    echo "  IP: $ip"
    echo "  SSH: ssh root@$ip"
    echo ""
    echo "Next: add Cloudflare A record voxforge.brohammad.tech → $ip (DNS only)"
    echo "Then: ssh root@$ip 'git clone https://github.com/Brohammad/VoxForge.git /opt/VoxForge && cd /opt/VoxForge && ./scripts/bootstrap-server.sh'"
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for IP. Check DigitalOcean console for droplet $DROPLET_ID"
exit 1
