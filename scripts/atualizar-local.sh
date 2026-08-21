#!/usr/bin/env bash
set -euo pipefail

cd "${DEVPILOT_HOME:-$HOME/Documents/devpilot}"

TARGET_BRANCH="${DEVPILOT_DEPLOY_BRANCH:-main}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_BRANCH="backup/local-before-update-${STAMP}"
STASH_CREATED=0

echo "=========================================="
echo " DEVPILOT - ATUALIZAR LOCAL"
echo "=========================================="

echo "=== ANTES ==="
git status -sb
git rev-parse --short HEAD

echo
echo "=== SALVANDO ESTADO LOCAL ==="
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ -n "$(git status --porcelain)" ]; then
  git stash push -u -m "devpilot-auto-update-${STAMP}"
  STASH_CREATED=1
  echo "Alterações não commitadas preservadas no stash."
fi

git fetch origin --prune

if git show-ref --verify --quiet "refs/remotes/origin/${TARGET_BRANCH}"; then
  AHEAD_COUNT="$(git rev-list --count "origin/${TARGET_BRANCH}..HEAD" 2>/dev/null || echo 0)"
  if [ "${AHEAD_COUNT}" -gt 0 ] || [ "${CURRENT_BRANCH}" != "${TARGET_BRANCH}" ]; then
    if ! git show-ref --verify --quiet "refs/heads/${BACKUP_BRANCH}"; then
      git branch "${BACKUP_BRANCH}" HEAD
      echo "Backup criado: ${BACKUP_BRANCH}"
    fi
  fi
else
  echo "ERRO: origin/${TARGET_BRANCH} não existe."
  exit 1
fi

echo
echo "=== SINCRONIZANDO BRANCH CANÔNICA ==="
if git show-ref --verify --quiet "refs/heads/${TARGET_BRANCH}"; then
  git switch "${TARGET_BRANCH}"
else
  git switch -c "${TARGET_BRANCH}" "origin/${TARGET_BRANCH}"
fi

git reset --hard "origin/${TARGET_BRANCH}"
git branch --set-upstream-to="origin/${TARGET_BRANCH}" "${TARGET_BRANCH}" >/dev/null 2>&1 || true

echo "Branch ativa: $(git rev-parse --abbrev-ref HEAD)"
echo "Commit remoto aplicado: $(git rev-parse --short HEAD)"

if [ "${STASH_CREATED}" -eq 1 ]; then
  echo "IMPORTANTE: seu trabalho local ficou preservado em stash e NÃO foi reaplicado sobre a versão de teste."
  echo "Use 'git stash list' para consultar depois."
fi

echo
echo "=== INSTALANDO COMANDOS E TELEMETRIA BASH ==="
bash scripts/instalar-aliases-linux.sh

echo
echo "=== CORRIGINDO REPETAI LOCAL ==="
if ! python3 scripts/corrigir-repeatai-mobile.py; then
  echo "AVISO: não foi possível aplicar automaticamente a correção mobile do RepetAI."
  echo "O update do DevPilot continuará; revise a mensagem acima."
fi

echo
echo "=== PREPARANDO HOST ACTIONS ==="
# O init cria as filas e corrige permissões do bind mount sem trocar o dono do host.
docker compose run --rm host-actions-init

echo
echo "=== REBUILD SEGURO ==="
docker compose build --pull app worker
docker compose up -d --force-recreate app worker postgres

echo
echo "=== AGUARDANDO API ==="
for i in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8080/health; then
    echo
    echo "=========================================="
    echo " DEVPILOT = OK"
    echo " URL: http://127.0.0.1:8080"
    echo " TELEMETRIA: hook Bash instalado"
    echo " BRANCH: $(git rev-parse --abbrev-ref HEAD)"
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
