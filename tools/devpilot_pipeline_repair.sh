#!/usr/bin/env bash
set -euo pipefail

ROOT="${DEVPILOT_ROOT:-$HOME/Documents/devpilot}"
cd "$ROOT"

log() { printf '%s\n' "$*"; }

log '=== DEVPILOT PIPELINE REPAIR ==='
log '1/6 garantindo postgres e redis'
docker compose up -d postgres redis

log '2/6 removendo somente worker antigo'
docker compose stop worker >/dev/null 2>&1 || true
docker compose rm -f worker >/dev/null 2>&1 || true

log '3/6 recriando worker na rede compose atual'
docker compose up -d worker
sleep 5

log '4/6 validando DNS postgres dentro do worker'
docker compose exec -T worker python - <<'PY'
import socket
ip = socket.gethostbyname('postgres')
print(f'POSTGRES_DNS=OK {ip}')
PY

log '5/6 validando conexão do worker com banco'
docker compose exec -T worker python - <<'PY'
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DEVPILOT_DATABASE_URL'])
with engine.connect() as conn:
    value = conn.execute(text('select 1')).scalar()
print(f'WORKER_POSTGRES=OK {value}')
PY

log '6/6 validando worker e fila'
sleep 4
docker compose logs --since=30s --tail=80 worker || true

log 'PIPELINE_REPAIR=OK'
