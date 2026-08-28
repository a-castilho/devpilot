#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HEALTH_URL="${DEVPILOT_URL:-http://127.0.0.1:8080}/health"
COMPOSE=(docker compose)

log() { printf '[subir-projeto] %s\n' "$*"; }

fail_report() {
  local rc=$?
  if ((rc != 0)); then
    log "Falha na subida. Estado atual:"
    "${COMPOSE[@]}" ps 2>/dev/null || true
  fi
  exit "$rc"
}
trap fail_report EXIT

command -v docker >/dev/null 2>&1 || { log "ERRO: docker não encontrado."; exit 1; }
docker compose version >/dev/null 2>&1 || { log "ERRO: plugin 'docker compose' não disponível."; exit 1; }

cd "$ROOT"
[[ -f docker-compose.yml || -f compose.yml || -f compose.yaml ]] || {
  log "ERRO: arquivo Docker Compose não encontrado em $ROOT."
  exit 1
}

mapfile -t SERVICES < <("${COMPOSE[@]}" config --services)
has_service() {
  local wanted="$1" service
  for service in "${SERVICES[@]}"; do
    [[ "$service" == "$wanted" ]] && return 0
  done
  return 1
}

wait_database() {
  local max_attempts="${1:-90}" attempt stable=0 db_user db_name result
  db_user="$("${COMPOSE[@]}" exec -T postgres printenv POSTGRES_USER 2>/dev/null || true)"
  db_name="$("${COMPOSE[@]}" exec -T postgres printenv POSTGRES_DB 2>/dev/null || true)"
  db_user="${db_user:-devpilot}"
  db_name="${db_name:-devpilot}"

  log "Aguardando PostgreSQL aceitar consultas de forma estável..."
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    result="$("${COMPOSE[@]}" exec -T postgres psql -U "$db_user" -d "$db_name" -tAc 'SELECT 1' 2>/dev/null | tr -d '[:space:]' || true)"
    if [[ "$result" == "1" ]]; then
      ((stable+=1))
      if ((stable >= 3)); then
        log "PostgreSQL pronto e estável."
        return 0
      fi
    else
      stable=0
    fi
    sleep 1
  done

  log "ERRO: PostgreSQL não ficou pronto dentro do limite."
  "${COMPOSE[@]}" logs --tail=80 postgres || true
  return 1
}

wait_init_service() {
  local service="$1" max_attempts="${2:-90}" attempt cid status exit_code
  has_service "$service" || return 0

  log "Executando inicializador: $service"
  "${COMPOSE[@]}" up -d "$service"

  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    cid="$("${COMPOSE[@]}" ps -a -q "$service" 2>/dev/null | head -n 1)"
    if [[ -n "$cid" ]]; then
      status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
      exit_code="$(docker inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || true)"
      if [[ "$status" == "exited" ]]; then
        if [[ "$exit_code" == "0" ]]; then
          log "$service concluído com sucesso."
          return 0
        fi
        log "ERRO: $service terminou com exit code ${exit_code:-desconhecido}."
        "${COMPOSE[@]}" logs --tail=80 "$service" || true
        return 1
      fi
      if [[ "$status" == "dead" ]]; then
        log "ERRO: $service entrou em estado dead."
        "${COMPOSE[@]}" logs --tail=80 "$service" || true
        return 1
      fi
    fi
    sleep 1
  done

  log "ERRO: $service não concluiu dentro do limite."
  "${COMPOSE[@]}" logs --tail=80 "$service" || true
  return 1
}

wait_app_health() {
  local max_attempts="${1:-90}" attempt body
  log "Aguardando health check do DevPilot..."
  for ((attempt=1; attempt<=max_attempts; attempt++)); do
    body="$(curl -fsS --max-time 3 "$HEALTH_URL" 2>/dev/null || true)"
    if grep -Eq '"service"[[:space:]]*:[[:space:]]*"devpilot"' <<<"$body"; then
      log "DevPilot saudável: $body"
      return 0
    fi
    sleep 1
  done

  log "ERRO: app não respondeu com health válido."
  "${COMPOSE[@]}" logs --tail=120 app || true
  return 1
}

check_worker() {
  local cid status
  has_service worker || return 0
  cid="$("${COMPOSE[@]}" ps -q worker 2>/dev/null | head -n 1)"
  [[ -n "$cid" ]] || { log "ERRO: worker não possui container em execução."; return 1; }
  status="$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
  if [[ "$status" != "running" ]]; then
    log "ERRO: worker está em estado ${status:-desconhecido}."
    "${COMPOSE[@]}" logs --tail=100 worker || true
    return 1
  fi
  log "Worker em execução."
}

has_service postgres || { log "ERRO: serviço postgres não existe no Compose."; exit 1; }
has_service app || { log "ERRO: serviço app não existe no Compose."; exit 1; }

log "Subindo PostgreSQL..."
"${COMPOSE[@]}" up -d postgres
wait_database

wait_init_service host-actions-init
wait_init_service codex-auth-init

CORE_SERVICES=(app)
has_service worker && CORE_SERVICES+=(worker)
log "Subindo serviços principais: ${CORE_SERVICES[*]}"
"${COMPOSE[@]}" up -d "${CORE_SERVICES[@]}"

wait_app_health
sleep 2
check_worker

log "Estado final:"
"${COMPOSE[@]}" ps
log "OK: projeto disponível em ${DEVPILOT_URL:-http://127.0.0.1:8080}"
trap - EXIT
