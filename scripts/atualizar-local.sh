#!/usr/bin/env bash
set -euo pipefail

cd "${DEVPILOT_HOME:-$HOME/Documents/devpilot}"

echo "=========================================="
echo " DEVPILOT - ATUALIZAR LOCAL"
echo "=========================================="

echo "=== ANTES ==="
git status -sb
git rev-parse --short HEAD

echo
echo "=== ATUALIZANDO GIT ==="
git fetch origin
git merge --ff-only origin/main

echo
echo "=== PREPARANDO HOST ACTIONS ==="
mkdir -p runtime/host-actions/{pending,processed,failed}
docker compose run --rm host-actions-init

echo
echo "=== REBUILD SEGURO ==="
docker compose build app worker
docker compose up -d --force-recreate app worker postgres

echo
echo "=== AGUARDANDO API ==="
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8080/health; then
    echo
    echo "=========================================="
    echo " DEVPILOT = OK"
    echo " URL: http://127.0.0.1:8080"
    echo " COMMIT: $(git rev-parse --short HEAD)"
    echo "=========================================="
    docker compose ps
    exit 0
  fi
  echo "Tentativa $i/30..."
  sleep 2
done

echo
echo "=== FALHA DE STARTUP ==="
docker compose ps -a
docker compose logs --no-color --tail=200 app
exit 1
