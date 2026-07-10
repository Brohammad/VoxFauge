#!/usr/bin/env bash
# Add Cloudflare DNS A record for voxforge.brohammad.tech (optional automation).
#
# Requires:
#   export CF_API_TOKEN=...   (Zone.DNS edit permission)
#   export CF_ZONE_ID=...     (zone ID for brohammad.tech)
#   export DROPLET_IP=...

set -euo pipefail

: "${CF_API_TOKEN:?Set CF_API_TOKEN}"
: "${CF_ZONE_ID:?Set CF_ZONE_ID}"
: "${DROPLET_IP:?Set DROPLET_IP}"

NAME="${DNS_NAME:-voxforge}"

payload=$(cat <<EOF
{
  "type": "A",
  "name": "$NAME",
  "content": "$DROPLET_IP",
  "ttl": 300,
  "proxied": false
}
EOF
)

curl -fsS -X POST "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$payload" | python3 -c "
import sys, json
r = json.load(sys.stdin)
if r.get('success'):
    print('DNS record created:', r['result']['name'], '→', r['result']['content'])
else:
    print('Failed:', r.get('errors'), file=sys.stderr)
    sys.exit(1)
"

echo "Verify: dig +short ${NAME}.brohammad.tech"
