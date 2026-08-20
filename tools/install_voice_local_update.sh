#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${DEVPILOT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
QUEUE_ROOT="$ROOT/runtime/host-actions"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_DIR/devpilot-host-actions.service"
PATH_FILE="$SYSTEMD_DIR/devpilot-host-actions.path"
PYTHON_BIN="$(command -v python3)"

mkdir -p "$QUEUE_ROOT/pending" "$QUEUE_ROOT/processed" "$QUEUE_ROOT/failed" "$SYSTEMD_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=DevPilot Linux host action runner
After=default.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT
Environment="DEVPILOT_ROOT=$ROOT"
Environment="DEVPILOT_HOST_ACTIONS_DIR=$QUEUE_ROOT"
ExecStart=$PYTHON_BIN $ROOT/tools/devpilot_host_action_runner.py
EOF

cat > "$PATH_FILE" <<EOF
[Unit]
Description=Watch DevPilot voice host action queue

[Path]
PathChanged=$QUEUE_ROOT/pending
Unit=devpilot-host-actions.service

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now devpilot-host-actions.path

cd "$ROOT"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
  docker compose build app worker
  docker compose up -d --force-recreate app worker
fi

printf '\n=== VOICE LOCAL UPDATE ===\n'
printf 'ROOT=%s\n' "$ROOT"
printf 'PATH_UNIT=' 
systemctl --user is-active devpilot-host-actions.path
printf 'HEALTH=' 
if curl -fsS http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo OK
else
  echo 'PENDING/VERIFY http://127.0.0.1:8080/health'
fi
printf 'COMANDO DE VOZ: atualizar local\n'
