#!/bin/sh
set -e

if [ "${APP_ENV:-development}" = "production" ]; then
  echo "Validating production environment..."
  python /app/scripts/validate_production_env.py
fi

echo "Running Alembic migrations..."
alembic upgrade head

if [ "${DEMO_ENABLED:-false}" = "true" ]; then
  echo "Synchronizing demo account..."
  python /app/scripts/ensure_demo_account.py
fi

echo "Starting VoxForge API..."
exec "$@"
