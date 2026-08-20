#!/usr/bin/env bash
set -euo pipefail

cd "${DEVPILOT_HOME:-$HOME/Documents/devpilot}"

echo "=========================================="
echo " DEVPILOT - RECONSTRUIR SISTEMA"
echo "=========================================="

echo "=== GIT ==="
git fetch origin
git merge --ff-only origin/main

echo
echo "=== PREPARANDO HOST ACTIONS ==="
mkdir -p runtime/host-actions/{pending,processed,failed}
docker compose run --rm host-actions-init

echo
echo "=== PARANDO SERVICOS SEM APAGAR DADOS ==="
docker compose down

echo
echo "=== REBUILD COMPLETO ==="
COMPOSE_PARALLEL_LIMIT=1 docker compose build --no-cache app worker

echo
echo "=== SUBINDO SISTEMA ==="
docker compose up -d --force-recreate postgres app worker

echo
echo "=== AGUARDANDO API ==="
for i in $(seq 1 40); do
  if curl -fsS --max-time 3 http://127.0.0.1:8080/health; then
    echo
    echo "=========================================="
    echo " RECONSTRUCAO = OK"
    echo " URL: http://127.0.0.1:8080"
    echo " COMMIT: $(git rev-parse --short HEAD)"
    echo "=========================================="
    docker compose ps
    exit 0
  fi
  echo "Tentativa $i/40..."
  sleep 2
done

echo
echo "=== FALHA DE STARTUP ==="
docker compose ps -a
docker compose logs --no-color --tail=250 app
exit 1
