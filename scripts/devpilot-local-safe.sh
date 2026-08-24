#!/usr/bin/env bash
set -Eeuo pipefail

PORT="${DEVPILOT_PORT:-8080}"
HOST="${DEVPILOT_HOST:-0.0.0.0}"
LOG_FILE="${DEVPILOT_LOG_FILE:-/tmp/devpilot.log}"
PID_FILE="${DEVPILOT_PID_FILE:-/tmp/devpilot-${PORT}.pid}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="http://127.0.0.1:${PORT}/health"

log() { printf '[devpilot] %s\n' "$*"; }

health_ok() {
  curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}

wait_for_health() {
  local attempts="${1:-24}"
  local i
  for ((i=1; i<=attempts; i++)); do
    if health_ok; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

start_server() {
  : >"$LOG_FILE"
  nohup "$ROOT/.venv/bin/python" -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    >"$LOG_FILE" 2>&1 &
  local pid=$!
  printf '%s\n' "$pid" >"$PID_FILE"
  log "Processo iniciado com PID $pid; aguardando health check..."
}

stop_server() {
  local stopped=0
  local pid=''

  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
      log "Encerrando PID registrado $pid..."
      kill -TERM "$pid" 2>/dev/null || true
      stopped=1
    fi
  fi

  mapfile -t fallback_pids < <(pgrep -f "[u]vicorn app.main:app.*--port ${PORT}" 2>/dev/null || true)
  if ((${#fallback_pids[@]})); then
    for pid in "${fallback_pids[@]}"; do
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      if kill -0 "$pid" 2>/dev/null; then
        log "Encerrando processo antigo $pid..."
        kill -TERM "$pid" 2>/dev/null || true
        stopped=1
      fi
    done
  fi

  if ((stopped)); then
    for _ in {1..20}; do
      health_ok || break
      sleep 0.25
    done
  fi

  rm -f "$PID_FILE"
}

cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  log "ERRO: ambiente .venv não encontrado. Nada foi encerrado."
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  log "ERRO: existem alterações locais não commitadas. Nada foi atualizado nem encerrado."
  git status --short
  exit 1
fi

BEFORE_SHA="$(git rev-parse HEAD)"
WAS_HEALTHY=0
health_ok && WAS_HEALTHY=1

log "Atualizando main sem interromper o servidor atual..."
git fetch origin main
git merge --ff-only origin/main
AFTER_SHA="$(git rev-parse HEAD)"

log "Validando código antes do restart..."
if ! "$ROOT/.venv/bin/python" -m compileall -q app; then
  log "Preflight falhou em compileall. Restaurando commit anterior e mantendo o processo atual."
  git reset --hard "$BEFORE_SHA"
  exit 1
fi

if ! "$ROOT/.venv/bin/python" -c 'from app.main import app; assert app.title'; then
  log "Preflight falhou ao importar app.main. Restaurando commit anterior e mantendo o processo atual."
  git reset --hard "$BEFORE_SHA"
  exit 1
fi

if [[ "${DEVPILOT_SAFE_RUN_TESTS:-0}" == "1" ]]; then
  log "Executando testes opcionais antes do restart..."
  if ! "$ROOT/.venv/bin/python" -m pytest -q tests/test_executor_development.py tests/test_executor_read_only.py; then
    log "Testes falharam. Restaurando commit anterior e mantendo o processo atual."
    git reset --hard "$BEFORE_SHA"
    exit 1
  fi
fi

log "Preflight aprovado em ${AFTER_SHA:0:7}. Só agora o processo antigo será reiniciado."
stop_server
start_server

if wait_for_health 30; then
  log "OK: DevPilot saudável em $HEALTH_URL"
  log "LOCAL: http://127.0.0.1:${PORT}"
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "$LAN_IP" ]] && log "REDE:  http://${LAN_IP}:${PORT}"
  exit 0
fi

log "ERRO: a nova versão não respondeu ao health check."
tail -n 80 "$LOG_FILE" 2>/dev/null || true

if [[ "$AFTER_SHA" != "$BEFORE_SHA" ]]; then
  log "Rollback automático para ${BEFORE_SHA:0:7}..."
  stop_server
  git reset --hard "$BEFORE_SHA"
  start_server
  if wait_for_health 30; then
    log "ROLLBACK OK: versão anterior restaurada e saudável."
    exit 1
  fi
fi

if ((WAS_HEALTHY)); then
  log "ERRO CRÍTICO: o serviço anterior estava saudável, mas não pôde ser restaurado automaticamente."
else
  log "O serviço já estava indisponível antes desta tentativa."
fi
log "Últimas linhas do log:"
tail -n 80 "$LOG_FILE" 2>/dev/null || true
exit 1
