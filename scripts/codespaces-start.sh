#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

if [ ! -f .env ]; then
  cp .env.example .env
fi

mkdir -p data runtime/host-actions

HOST="${DEVPILOT_HOST:-0.0.0.0}"
PORT="${DEVPILOT_PORT:-8080}"

echo "DevPilot Codespaces: http://${HOST}:${PORT}"
echo "Worker separado (opcional): python -m app.worker"
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
