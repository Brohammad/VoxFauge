#!/usr/bin/env bash
# Post-deploy smoke tests for VoxForge production.
# Usage: BASE_URL=https://voxforge.brohammad.tech ./scripts/smoke-test.sh

set -euo pipefail

BASE_URL="${BASE_URL:-https://voxforge.brohammad.tech}"
BASE_URL="${BASE_URL%/}"

pass() { printf '  OK  %s\n' "$*"; }
fail() { printf '  FAIL %s\n' "$*" >&2; exit 1; }

check_status() {
  local path="$1" expected="$2"
  local code
  code=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL$path")
  [[ "$code" == "$expected" ]] || fail "$path expected HTTP $expected, got $code"
  pass "$path → $expected"
}

echo "Smoke tests for $BASE_URL"
echo

check_status "/" "200"
check_status "/demo" "200"
check_status "/dashboard" "200"
check_status "/api/v1/docs" "200"
check_status "/api/v1/health" "200"
check_status "/api/v1/metrics" "403"

ready=$(curl -sS "$BASE_URL/api/v1/ready")
echo "$ready" | grep -q '"database".*"ok"' || fail "/ready database not ok"
echo "$ready" | grep -q '"redis".*"ok"' || fail "/ready redis not ok"
pass "/api/v1/ready database + redis ok"

echo
echo "All smoke tests passed."
