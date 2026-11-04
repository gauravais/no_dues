#!/usr/bin/env bash
set -e

echo "Applying database migrations..."
uv run alembic upgrade head

echo "Starting application on port ${PORT:-8000}..."
exec uv run uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
