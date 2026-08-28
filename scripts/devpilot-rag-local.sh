#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker-compose.rag-local.yml"
RAG_WORKER_PID_FILE="${DEVPILOT_RAG_WORKER_PID_FILE:-/tmp/devpilot-rag-worker.pid}"
RAG_WORKER_LOG_FILE="${DEVPILOT_RAG_WORKER_LOG_FILE:-/tmp/devpilot-rag-worker.log}"

log() { printf '[devpilot-rag] %s\n' "$*"; }

is_rag_worker_pid() {
  local pid="$1" cmd
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  cmd="$(tr '\0' ' ' <"/proc/${pid}/cmdline" 2>/dev/null || true)"
  [[ "$cmd" == *"python"* && "$cmd" == *"-m app.rag_worker_entry"* ]]
}

stop_rag_worker() {
  local pid=""
  [[ -f "$RAG_WORKER_PID_FILE" ]] || return 0
  pid="$(cat "$RAG_WORKER_PID_FILE" 2>/dev/null || true)"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    if ! is_rag_worker_pid "$pid"; then
      log "ERRO: PID $pid não pertence ao worker RAG; nada será encerrado."
      return 1
    fi
    log "Encerrando worker RAG anterior PID $pid..."
    kill -TERM "$pid"
    for _ in $(seq 1 20); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      log "ERRO: worker RAG não encerrou dentro do limite seguro."
      return 1
    fi
  fi
  rm -f "$RAG_WORKER_PID_FILE"
}

start_rag_worker() {
  stop_rag_worker
  : >"$RAG_WORKER_LOG_FILE"
  nohup "$ROOT/.venv/bin/python" -m app.rag_worker_entry >"$RAG_WORKER_LOG_FILE" 2>&1 &
  local pid=$!
  printf '%s\n' "$pid" >"$RAG_WORKER_PID_FILE"
  sleep 1
  if ! kill -0 "$pid" 2>/dev/null || ! is_rag_worker_pid "$pid"; then
    log "ERRO: worker RAG não iniciou corretamente."
    tail -n 40 "$RAG_WORKER_LOG_FILE" 2>/dev/null || true
    return 1
  fi
  log "Worker RAG ativo: pid=$pid log=$RAG_WORKER_LOG_FILE"
}

cd "$ROOT"
[[ -x .venv/bin/python ]] || { log "ERRO: .venv não encontrado."; exit 1; }
command -v docker >/dev/null 2>&1 || { log "ERRO: Docker não encontrado."; exit 1; }
docker compose version >/dev/null 2>&1 || { log "ERRO: Docker Compose não disponível."; exit 1; }

log "Subindo PostgreSQL/pgvector e Redis locais..."
docker compose -f "$COMPOSE_FILE" up -d rag-postgres rag-redis

log "Aguardando pgvector e Redis ficarem saudáveis..."
for _ in $(seq 1 40); do
  if docker compose -f "$COMPOSE_FILE" exec -T rag-postgres pg_isready -U devpilot -d devpilot_rag >/dev/null 2>&1 \
    && [[ "$(docker compose -f "$COMPOSE_FILE" exec -T rag-redis redis-cli ping 2>/dev/null || true)" == "PONG" ]]; then
    break
  fi
  sleep 1
done

docker compose -f "$COMPOSE_FILE" exec -T rag-postgres pg_isready -U devpilot -d devpilot_rag >/dev/null
[[ "$(docker compose -f "$COMPOSE_FILE" exec -T rag-redis redis-cli ping)" == "PONG" ]] || { log "ERRO: Redis RAG não respondeu PONG."; exit 1; }

export DEVPILOT_RAG_DATABASE_URL="${DEVPILOT_RAG_DATABASE_URL:-postgresql+psycopg://devpilot:devpilot@127.0.0.1:55432/devpilot_rag}"
export DEVPILOT_REDIS_URL="${DEVPILOT_REDIS_URL:-redis://127.0.0.1:56379/0}"
export DEVPILOT_RAG_ENABLED="${DEVPILOT_RAG_ENABLED:-1}"

log "Inicializando schema RAG isolado..."
"$ROOT/.venv/bin/python" -c 'from app.config import get_settings; from app.rag.database import rag_engine; from app.rag.schema import ensure_rag_schema; assert rag_engine is not None; assert ensure_rag_schema(rag_engine, embedding_dimensions=get_settings().rag_embedding_dimensions)'

log "Validando provedor de embeddings sem expor credenciais..."
"$ROOT/.venv/bin/python" -c 'from app.rag.runtime import get_rag_embedder; import sys; sys.exit(0) if get_rag_embedder() is not None else sys.exit("Configure DEVPILOT_RAG_EMBEDDING_API_KEY no .env ou OPENAI_API_KEY no ambiente.")'

log "Atualizando/reiniciando o DevPilot com o backend RAG isolado..."
bash "$ROOT/scripts/devpilot-local-safe.sh"

start_rag_worker

log "RAG local pronto: PostgreSQL/pgvector=127.0.0.1:55432 Redis=127.0.0.1:56379"
log "Indexar / Atualizar já pode enfileirar e processar documentos no banco vetorial isolado."
