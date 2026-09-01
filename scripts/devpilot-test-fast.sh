#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PULL=1
FORCE_REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=0 ;;
    --force-rebuild) FORCE_REBUILD=1 ;;
    *) echo "Argumento desconhecido: $arg" >&2; exit 2 ;;
  esac
done

# O override de teste nunca deve ser executado sozinho. Ele apenas adiciona bind
# mounts aos serviços definidos no compose principal.
COMPOSE=(docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.test.yml")
BEFORE="$(git rev-parse HEAD)"

if [[ "$PULL" == "1" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    git stash push -u -m "backup-antes-fast-test-$(date +%Y%m%d-%H%M%S)"
  fi
  git fetch --all --prune
  git switch main
  git pull --ff-only origin main
fi

AFTER="$(git rev-parse HEAD)"
if [[ "$BEFORE" == "$AFTER" ]]; then
  CHANGED=""
else
  CHANGED="$(git diff --name-only "$BEFORE..$AFTER")"
fi

needs_rebuild=0
needs_python_restart=0
needs_worker_restart=0

if [[ "$FORCE_REBUILD" == "1" ]]; then
  needs_rebuild=1
fi

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  case "$file" in
    Dockerfile|pyproject.toml|requirements*.txt)
      needs_rebuild=1
      ;;
    app/*.py|app/**/*.py)
      needs_python_restart=1
      needs_worker_restart=1
      ;;
    app/*)
      # Arquivos não estáticos dentro de app podem ser importados/lidos em memória.
      if [[ "$file" != app/static/* ]]; then
        needs_python_restart=1
      fi
      ;;
  esac
done <<< "$CHANGED"

echo "=== DEVPILOT FAST TEST ==="
echo "ANTES=$BEFORE"
echo "AGORA=$AFTER"
if [[ -n "$CHANGED" ]]; then
  echo "=== ALTERAÇÕES RECEBIDAS ==="
  printf '%s\n' "$CHANGED"
else
  echo "ALTERACOES_RECEBIDAS=0"
fi

echo "=== VALIDANDO COMPOSE RÁPIDO ==="
"${COMPOSE[@]}" config >/tmp/devpilot-fast-compose.yml
for service in app worker rag-worker; do
  if ! "${COMPOSE[@]}" config --services | grep -Fxq "$service"; then
    echo "FAST_TEST=COMPOSE_SERVICO_AUSENTE:$service" >&2
    exit 1
  fi
done
echo "COMPOSE_FAST=OK"

if [[ "$needs_rebuild" == "1" ]]; then
  echo "=== MODO: REBUILD COM CACHE ==="
  "${COMPOSE[@]}" build app worker rag-worker
  "${COMPOSE[@]}" up -d app worker rag-worker
elif [[ "$needs_worker_restart" == "1" ]]; then
  echo "=== MODO: PYTHON + WORKERS (SEM REBUILD FORÇADO) ==="
  # Não usamos --no-build: versões antigas do Compose tratam serviços apenas
  # com build: como inválidos nesse modo. Sem --build, a imagem existente é
  # reutilizada normalmente e só é criada se ainda não existir.
  "${COMPOSE[@]}" up -d app worker rag-worker
  "${COMPOSE[@]}" restart app worker rag-worker
elif [[ "$needs_python_restart" == "1" ]]; then
  echo "=== MODO: PYTHON APP (SEM REBUILD FORÇADO) ==="
  "${COMPOSE[@]}" up -d app
  "${COMPOSE[@]}" restart app
else
  echo "=== MODO: FRONTEND/HOT MOUNT (SEM REBUILD FORÇADO E SEM RESTART) ==="
  # Na primeira execução o Compose recria o app para aplicar o bind mount.
  # Nas seguintes, mudanças em app/static ficam visíveis imediatamente.
  # Não passe --no-build aqui: no Compose presente no Ubuntu de teste ele
  # elimina build: da resolução do serviço e causa "Must specify image or build".
  "${COMPOSE[@]}" up -d app
fi

rm -f /tmp/devpilot-fast-health.json
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8080/health >/tmp/devpilot-fast-health.json 2>/dev/null; then
    break
  fi
  sleep 1
done

if [[ ! -s /tmp/devpilot-fast-health.json ]]; then
  echo "FAST_TEST=FALHA_HEALTH" >&2
  exit 1
fi

echo "=== HEALTH ==="
cat /tmp/devpilot-fast-health.json
echo

# Confirma que o bind mount está servindo exatamente o arquivo estático local.
if [[ -f app/static/feature-loader.js ]]; then
  curl -fsS http://127.0.0.1:8080/assets/feature-loader.js -o /tmp/devpilot-fast-feature-loader.js
  host_sha="$(sha256sum app/static/feature-loader.js | awk '{print $1}')"
  served_sha="$(sha256sum /tmp/devpilot-fast-feature-loader.js | awk '{print $1}')"
  if [[ "$host_sha" != "$served_sha" ]]; then
    echo "FAST_TEST=ASSET_DESATUALIZADO" >&2
    echo "HOST_SHA=$host_sha" >&2
    echo "SERVED_SHA=$served_sha" >&2
    exit 1
  fi
  echo "ASSET_BIND_MOUNT=OK"
fi

echo "FAST_TEST=APROVADO"
echo "URL=http://127.0.0.1:8080"
