#!/usr/bin/env bash
# Validate production stack locally without TLS (postgres + redis + app only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose -f $ROOT/docker-compose.prod.yml -f $ROOT/docker-compose.smoke.yml"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"

_smoke_port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1
    return
  fi
  curl -fsS "http://127.0.0.1:${port}/api/v1/health" >/dev/null 2>&1
}

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating $ENV_FILE via setup-production-env.sh localhost.test"
  "$ROOT/scripts/setup-production-env.sh" localhost.test
fi

SMOKE_APP_PORT="${SMOKE_APP_PORT:-8000}"
if _smoke_port_in_use "$SMOKE_APP_PORT"; then
  for candidate in 8766 8877 8988; do
    if ! _smoke_port_in_use "$candidate"; then
      echo "Port $SMOKE_APP_PORT in use; using $candidate for smoke test"
      SMOKE_APP_PORT="$candidate"
      break
    fi
  done
fi
export SMOKE_APP_PORT

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Local smoke uses HTTP localhost — override production URL checks for this run only.
export PUBLIC_BASE_URL="http://127.0.0.1:${SMOKE_APP_PORT}"
export TRUSTED_HOSTS="${TRUSTED_HOSTS:-localhost,127.0.0.1}"
export CORS_ORIGINS="http://127.0.0.1:${SMOKE_APP_PORT}"

cleanup() {
  $COMPOSE --env-file "$ENV_FILE" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Stopping any previous smoke stack"
$COMPOSE --env-file "$ENV_FILE" down --remove-orphans >/dev/null 2>&1 || true

echo "==> Building production image"
$COMPOSE --env-file "$ENV_FILE" build app

echo "==> Starting core services (no nginx/certbot) on port ${SMOKE_APP_PORT}"
$COMPOSE --env-file "$ENV_FILE" up -d postgres redis app

BASE_URL="http://127.0.0.1:${SMOKE_APP_PORT}"
echo "==> Waiting for readiness at ${BASE_URL}"
for _ in $(seq 1 60); do
  if curl -fsS "${BASE_URL}/api/v1/ready" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS "${BASE_URL}/api/v1/health" | tee /tmp/voxforge-smoke-health.json
curl -fsS "${BASE_URL}/api/v1/ready" | tee /tmp/voxforge-smoke-ready.json
curl -fsS -o /dev/null -w "landing:%{http_code}\n" "${BASE_URL}/"
curl -fsS -o /dev/null -w "demo:%{http_code}\n" "${BASE_URL}/demo"
curl -fsS -o /dev/null -w "dashboard:%{http_code}\n" "${BASE_URL}/dashboard"

echo "==> Production smoke passed (port ${SMOKE_APP_PORT})"
