#!/usr/bin/env bash
set -euo pipefail

# Wait for DB if it's Postgres (compose healthcheck already covers most cases)
echo "[entrypoint] Running migrations..."
alembic upgrade head

echo "[entrypoint] Starting app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000

