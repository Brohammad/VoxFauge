#!/usr/bin/env bash
# Validate production stack locally without TLS (postgres + redis + app only).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE="docker compose -f $ROOT/docker-compose.prod.yml -f $ROOT/docker-compose.smoke.yml"
ENV_FILE="${ENV_FILE:-$ROOT/.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Creating $ENV_FILE via setup-production-env.sh localhost.test"
  "$ROOT/scripts/setup-production-env.sh" localhost.test
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Local smoke uses HTTP localhost — override production URL checks for this run only.
export PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-http://localhost:8000}"
export TRUSTED_HOSTS="${TRUSTED_HOSTS:-localhost,127.0.0.1}"
export CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:8000}"

echo "==> Building production image"
$COMPOSE --env-file "$ENV_FILE" build app

echo "==> Starting core services (no nginx/certbot)"
$COMPOSE --env-file "$ENV_FILE" up -d postgres redis app

echo "==> Waiting for readiness"
for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/api/v1/ready >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

curl -fsS http://127.0.0.1:8000/api/v1/health | tee /tmp/voxforge-smoke-health.json
curl -fsS http://127.0.0.1:8000/api/v1/ready | tee /tmp/voxforge-smoke-ready.json
curl -fsS -o /dev/null -w "landing:%{http_code}\n" http://127.0.0.1:8000/
curl -fsS -o /dev/null -w "demo:%{http_code}\n" http://127.0.0.1:8000/demo
curl -fsS -o /dev/null -w "dashboard:%{http_code}\n" http://127.0.0.1:8000/dashboard

echo "==> Production smoke passed"
