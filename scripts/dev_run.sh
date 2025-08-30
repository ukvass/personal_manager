#!/usr/bin/env bash
set -euo pipefail

# Resolve pip and uvicorn: prefer project .venv if present
if [[ -x ".venv/bin/pip" ]] && [[ -x ".venv/bin/uvicorn" ]]; then
  PIP=".venv/bin/pip"
  UVICORN=".venv/bin/uvicorn"
else
  # Fallback to system
  PIP="python3 -m pip"
  UVICORN="python3 -m uvicorn"
fi

echo "[dev] Installing requirements (idempotent)..."
${PIP} install -r requirements.txt

echo "[dev] Starting app with reload..."
exec ${UVICORN} app.main:app --reload

