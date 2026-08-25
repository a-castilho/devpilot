#!/usr/bin/env bash
set -Eeuo pipefail

PORT="${DEVPILOT_PORT:-8080}"
HOST="${DEVPILOT_HOST:-0.0.0.0}"
LOG_FILE="${DEVPILOT_LOG_FILE:-/tmp/devpilot.log}"
PID_FILE="${DEVPILOT_PID_FILE:-/tmp/devpilot-${PORT}.pid}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="http://127.0.0.1:${PORT}/health"

log() { printf '[devpilot] %s\n' "$*"; }

health_body() {
  curl -fsS --max-time 2 "$HEALTH_URL" 2>/dev/null
}

health_ok() {
  local body
  body="$(health_body)" || return 1
  grep -Eq '"service"[[:space:]]*:[[:space:]]*"devpilot"' <<<"$body"
}

port_inspection_available() {
  command -v lsof >/dev/null 2>&1 || \
    command -v fuser >/dev/null 2>&1 || \
    command -v ss >/dev/null 2>&1
}

require_port_inspector() {
  if port_inspection_available; then
    return 0
  fi
  log "ERRO: não há lsof, fuser ou ss para identificar com segurança o dono da porta ${PORT}."
  log "Operação recusada: o runtime local trabalha em fail-closed quando a porta não pode ser inspecionada."
  return 1
}

port_has_listener() {
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltn "sport = :${PORT}" 2>/dev/null | grep -q .
    return $?
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | tail -n +2 | grep -q .
    return $?
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$PORT" >/dev/null 2>&1
    return $?
  fi
  return 2
}

port_listener_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -t -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | awk '/^[0-9]+$/' | sort -u
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$PORT" 2>/dev/null | tr ' ' '\n' | awk '/^[0-9]+$/' | sort -u
    return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -H -ltnp "sport = :${PORT}" 2>/dev/null \
      | grep -oE 'pid=[0-9]+' \
      | cut -d= -f2 \
      | sort -u || true
    return 0
  fi
  return 2
}

pid_command() {
  local pid="$1"
  tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true
}

is_known_devpilot_pid() {
  local pid="$1"
  local cmd
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  cmd="$(pid_command "$pid")"
  [[ "$cmd" == *"uvicorn"* && "$cmd" == *"app.main:app"* && "$cmd" == *"--port ${PORT}"* ]]
}

assert_port_is_safe() {
  local pid
  if ! require_port_inspector; then
    return 1
  fi

  mapfile -t listeners < <(port_listener_pids)
  if ((${#listeners[@]} == 0)); then
    if port_has_listener; then
      log "ERRO: porta ${PORT} possui listener, mas o PID não pôde ser identificado com segurança."
      log "Nada será encerrado ou iniciado automaticamente."
      return 1
    fi
    return 0
  fi

  if health_ok; then
    for pid in "${listeners[@]}"; do
      if ! is_known_devpilot_pid "$pid"; then
        log "ERRO: /health parece DevPilot, mas a porta ${PORT} também possui PID desconhecido ${pid}: $(pid_command "$pid")"
        return 1
      fi
    done
    return 0
  fi

  for pid in "${listeners[@]}"; do
    if ! is_known_devpilot_pid "$pid"; then
      log "ERRO: porta ${PORT} ocupada por processo desconhecido PID ${pid}: $(pid_command "$pid")"
      log "Nada será encerrado automaticamente. Libere a porta conscientemente e execute novamente."
      return 1
    fi
  done
  return 0
}

wait_for_port_free() {
  local attempts="${1:-20}"
  local i state
  for ((i=1; i<=attempts; i++)); do
    port_has_listener
    state=$?
    if ((state == 1)); then
      return 0
    fi
    if ((state == 2)); then
      return 1
    fi
    sleep 0.25
  done
  return 1
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

runtime_report() {
  local revision pid health_state
  revision="$(git rev-parse --short HEAD 2>/dev/null || printf 'desconhecida')"
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  health_state="FALHOU"
  health_ok && health_state="OK"
  log "RUNTIME: commit=${revision} porta=${PORT} pid=${pid:-desconhecido} health=${health_state} log=${LOG_FILE}"
}

start_server() {
  if ! assert_port_is_safe; then
    return 1
  fi
  if port_has_listener; then
    mapfile -t listeners < <(port_listener_pids)
    log "ERRO: recusando iniciar; porta ${PORT} ainda está ocupada por PID(s): ${listeners[*]:-desconhecido}"
    return 1
  fi

  : >"$LOG_FILE"
  nohup "$ROOT/.venv/bin/python" -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    >"$LOG_FILE" 2>&1 &
  local pid=$!
  printf '%s\n' "$pid" >"$PID_FILE"
  log "Processo iniciado com PID $pid; aguardando health check do DevPilot..."
}

stop_server() {
  local stopped=0
  local pid=''

  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && is_known_devpilot_pid "$pid"; then
      log "Encerrando PID registrado $pid..."
      kill -TERM "$pid" 2>/dev/null || true
      stopped=1
    fi
  fi

  mapfile -t fallback_pids < <(pgrep -f "[u]vicorn app.main:app.*--port ${PORT}" 2>/dev/null || true)
  if ((${#fallback_pids[@]})); then
    for pid in "${fallback_pids[@]}"; do
      [[ "$pid" =~ ^[0-9]+$ ]] || continue
      if kill -0 "$pid" 2>/dev/null && is_known_devpilot_pid "$pid"; then
        log "Encerrando processo DevPilot antigo $pid..."
        kill -TERM "$pid" 2>/dev/null || true
        stopped=1
      fi
    done
  fi

  if ((stopped)) && ! wait_for_port_free 24; then
    mapfile -t remaining < <(port_listener_pids)
    log "ERRO: porta ${PORT} não foi liberada após SIGTERM. PID(s): ${remaining[*]:-desconhecido}"
    return 1
  fi

  rm -f "$PID_FILE"
}

rollback_runtime() {
  local target_sha="$1"
  log "Rollback automático para ${target_sha:0:7}..."
  stop_server || true
  git reset --hard "$target_sha"
  if ! assert_port_is_safe; then
    log "ROLLBACK FALHOU: porta ${PORT} ficou sob controle de processo desconhecido."
    return 1
  fi
  if ! start_server; then
    log "ROLLBACK FALHOU: não foi possível iniciar a revisão anterior."
    return 1
  fi
  if wait_for_health 30; then
    log "ROLLBACK OK: versão anterior restaurada e saudável."
    runtime_report
    return 0
  fi
  log "ROLLBACK FALHOU: revisão anterior não respondeu com health válido."
  return 1
}

restore_after_shutdown_timeout() {
  local target_sha="$1"
  log "Restaurando checkout anterior ${target_sha:0:7} após timeout de shutdown..."
  git reset --hard "$target_sha"

  if health_ok; then
    log "Revisão anterior restaurada no checkout; processo antigo continua saudável."
    runtime_report
    return 0
  fi

  log "Aguardando a porta ${PORT} ser liberada para reativar a revisão anterior..."
  if wait_for_port_free 40; then
    if ! assert_port_is_safe; then
      return 1
    fi
    if ! start_server; then
      return 1
    fi
    if wait_for_health 30; then
      log "RECUPERAÇÃO OK: revisão anterior voltou após timeout de shutdown."
      runtime_report
      return 0
    fi
  fi

  # Última verificação: o processo antigo pode ter voltado a responder enquanto
  # aguardávamos. Nunca lançamos uma segunda instância sobre uma porta ocupada.
  if health_ok; then
    log "Revisão anterior está saudável após a espera de recuperação."
    runtime_report
    return 0
  fi

  log "RECUPERAÇÃO FALHOU: checkout anterior foi restaurado, mas o serviço não ficou saudável."
  return 1
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

if ! require_port_inspector; then
  exit 1
fi

if ! assert_port_is_safe; then
  exit 1
fi

BEFORE_SHA="$(git rev-parse HEAD)"
WAS_HEALTHY=0
health_ok && WAS_HEALTHY=1
runtime_report

log "Atualizando main sem interromper o servidor atual..."
git fetch origin main
git merge --ff-only origin/main
AFTER_SHA="$(git rev-parse HEAD)"

log "Validando política e código antes do restart..."
if ! "$ROOT/.venv/bin/python" scripts/check-engineering-standards.py --changed --base "$BEFORE_SHA"; then
  log "Preflight falhou no padrão de engenharia. Restaurando commit anterior e mantendo o processo atual."
  git reset --hard "$BEFORE_SHA"
  exit 1
fi

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
if ! stop_server; then
  log "ERRO: processo antigo não encerrou dentro do limite seguro. A nova versão não será iniciada."
  if ! restore_after_shutdown_timeout "$BEFORE_SHA"; then
    log "ERRO CRÍTICO: não foi possível garantir a continuidade da revisão anterior."
  fi
  exit 1
fi

if ! start_server; then
  log "ERRO: a nova versão não pôde ser iniciada."
  if [[ "$AFTER_SHA" != "$BEFORE_SHA" ]]; then
    rollback_runtime "$BEFORE_SHA" || true
  fi
  exit 1
fi

if wait_for_health 30; then
  log "OK: DevPilot saudável e identificado em $HEALTH_URL"
  runtime_report
  log "LOCAL: http://127.0.0.1:${PORT}"
  LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "$LAN_IP" ]] && log "REDE:  http://${LAN_IP}:${PORT}"
  exit 0
fi

log "ERRO: a nova versão não respondeu com health válido do DevPilot."
runtime_report
tail -n 80 "$LOG_FILE" 2>/dev/null || true

if [[ "$AFTER_SHA" != "$BEFORE_SHA" ]]; then
  if rollback_runtime "$BEFORE_SHA"; then
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
