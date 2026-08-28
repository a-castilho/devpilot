#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
RAG_URL="postgresql+psycopg://devpilot:devpilot@127.0.0.1:5433/devpilot"
RAG_LOG="${DEVPILOT_RAG_WORKER_LOG:-/tmp/devpilot-rag-worker.log}"
RAG_PID_FILE="${DEVPILOT_RAG_WORKER_PID_FILE:-/tmp/devpilot-rag-worker.pid}"

log() { printf '[devpilot-rag] %s\n' "$*"; }

cd "$ROOT"
command -v docker >/dev/null 2>&1 || { log "ERRO: Docker não está disponível."; exit 1; }
docker compose version >/dev/null 2>&1 || { log "ERRO: docker compose não está disponível."; exit 1; }
[[ -f "$ENV_FILE" ]] || cp .env.example "$ENV_FILE"

log "Subindo somente PostgreSQL + pgvector local..."
docker compose up -d postgres

for _ in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U devpilot -d devpilot >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker compose exec -T postgres pg_isready -U devpilot -d devpilot >/dev/null 2>&1 || {
  log "ERRO: PostgreSQL/pgvector não ficou saudável."; exit 1;
}

python3 - "$ENV_FILE" "$RAG_URL" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
value = sys.argv[2]
key = "DEVPILOT_RAG_DATABASE_URL"
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
updated = []
found = False
for line in lines:
    if line.startswith(key + "="):
        updated.append(f"{key}={value}")
        found = True
    else:
        updated.append(line)
if not found:
    updated.append(f"{key}={value}")
path.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")
PY

if "$ROOT/.venv/bin/python" -c 'from app.rag.runtime import embedding_key_configured; raise SystemExit(0 if embedding_key_configured() else 1)'; then
  log "Embeddings: usando credencial OpenAI disponível."
else
  log "Embeddings: nenhuma API key disponível; usando fallback local CPU-only, sem custo externo."
fi

log "Reiniciando o DevPilot pelo fluxo local seguro..."
bash scripts/devpilot-local-safe.sh

if [[ -f "$RAG_PID_FILE" ]]; then
  OLD_PID="$(cat "$RAG_PID_FILE" 2>/dev/null || true)"
  if [[ "$OLD_PID" =~ ^[0-9]+$ ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    OLD_CMD="$(tr '\0' ' ' <"/proc/${OLD_PID}/cmdline" 2>/dev/null || true)"
    if [[ "$OLD_CMD" == *"app.rag_worker_entry"* ]]; then
      log "Encerrando worker RAG anterior PID $OLD_PID..."
      kill -TERM "$OLD_PID" 2>/dev/null || true
      for _ in $(seq 1 20); do
        kill -0 "$OLD_PID" 2>/dev/null || break
        sleep 0.25
      done
    fi
  fi
fi

: >"$RAG_LOG"
nohup "$ROOT/.venv/bin/python" -m app.rag_worker_entry >"$RAG_LOG" 2>&1 &
RAG_PID=$!
printf '%s\n' "$RAG_PID" >"$RAG_PID_FILE"
sleep 1
kill -0 "$RAG_PID" 2>/dev/null || {
  log "ERRO: worker RAG não permaneceu ativo."; tail -n 40 "$RAG_LOG" 2>/dev/null || true; exit 1;
}

log "OK: pgvector local ativo em 127.0.0.1:5433; worker RAG PID $RAG_PID; log=$RAG_LOG"
