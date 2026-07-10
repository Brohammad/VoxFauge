#!/usr/bin/env bash
# Chaos / resilience checks (run on the VPS after deploy).
# Usage: BASE_URL=https://voxforge.brohammad.tech ./scripts/chaos-test.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose -f $ROOT/docker-compose.prod.yml --env-file $ROOT/.env.production"
BASE_URL="${BASE_URL:-https://voxforge.brohammad.tech}"
BASE_URL="${BASE_URL%/}"

ready_code() {
  curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/api/v1/ready"
}

log() { printf '==> %s\n' "$*"; }

log "Stopping Redis..."
$COMPOSE stop redis
sleep 3
code=$(ready_code)
[[ "$code" == "503" ]] || { echo "Expected 503 when Redis down, got $code"; exit 1; }
log "Redis down → /ready returned 503 (OK)"
$COMPOSE start redis
sleep 5

log "Stopping Postgres..."
$COMPOSE stop postgres
sleep 3
code=$(ready_code)
[[ "$code" == "503" ]] || { echo "Expected 503 when Postgres down, got $code"; exit 1; }
log "Postgres down → /ready returned 503 (OK)"
$COMPOSE start postgres
sleep 10

log "Restarting app..."
$COMPOSE restart app
sleep 5
code=$(ready_code)
[[ "$code" == "200" ]] || { echo "Expected 200 after recovery, got $code"; exit 1; }

if $COMPOSE ps --status running 2>/dev/null | grep -q livekit-worker; then
  log "Restarting livekit-worker..."
  $COMPOSE restart livekit-worker
fi

log "Chaos tests passed."
