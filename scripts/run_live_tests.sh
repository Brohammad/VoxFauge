#!/usr/bin/env bash
# Run the full VoxForge test suite including live provider tests.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example and fill in API keys."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

echo "==> Unit + integration tests"
.venv/bin/pytest tests/unit tests/integration -v --tb=short

echo ""
echo "==> Live provider tests"
.venv/bin/pytest tests/live -m live -v --tb=short

echo ""
echo "All tests passed."
