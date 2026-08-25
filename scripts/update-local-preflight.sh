#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${DEVPILOT_HOME:-$HOME/Documents/devpilot}"
TARGET_BRANCH="${DEVPILOT_DEPLOY_BRANCH:-main}"
MIN_AVAILABLE_KB="${DEVPILOT_UPDATE_MIN_AVAILABLE_KB:-524288}"
TEST_TIMEOUT="${DEVPILOT_UPDATE_TEST_TIMEOUT:-45}"

cd "$ROOT"

fail() {
  echo "ERRO: $*" >&2
  exit 1
}

mem_available_kb() {
  awk '/MemAvailable:/ {print $2}' /proc/meminfo
}

run_limited() {
  if command -v ionice >/dev/null 2>&1; then
    ionice -c3 nice -n 10 timeout --signal=TERM --kill-after=5s "${TEST_TIMEOUT}s" "$@"
  else
    nice -n 10 timeout --signal=TERM --kill-after=5s "${TEST_TIMEOUT}s" "$@"
  fi
}

[[ -d .git ]] || fail "$ROOT não é um checkout Git do DevPilot."
[[ "$(git rev-parse --abbrev-ref HEAD)" == "$TARGET_BRANCH" ]] || fail "use a branch $TARGET_BRANCH antes de atualizar."
[[ -z "$(git status --porcelain)" ]] || fail "há alterações locais; faça commit/stash antes da atualização segura."

AVAILABLE_KB="$(mem_available_kb)"
if [[ -z "$AVAILABLE_KB" || "$AVAILABLE_KB" -lt "$MIN_AVAILABLE_KB" ]]; then
  fail "RAM disponível insuficiente para validar com segurança (${AVAILABLE_KB:-0} KiB; mínimo ${MIN_AVAILABLE_KB} KiB)."
fi

echo "=== FETCH SEM ALTERAR O SISTEMA EM EXECUÇÃO ==="
git fetch --quiet origin "$TARGET_BRANCH" || fail "não foi possível buscar origin/$TARGET_BRANCH."
TARGET="origin/$TARGET_BRANCH"
CURRENT_SHA="$(git rev-parse HEAD)"
TARGET_SHA="$(git rev-parse "$TARGET")"
echo "Atual:  ${CURRENT_SHA:0:12}"
echo "Remoto: ${TARGET_SHA:0:12}"

if [[ "$CURRENT_SHA" == "$TARGET_SHA" ]]; then
  echo "OK: checkout já está atualizado."
  exit 0
fi

git merge-base --is-ancestor HEAD "$TARGET" || fail "origin/$TARGET_BRANCH não é fast-forward do checkout atual."

TMP_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/devpilot-preflight.XXXXXX")"
TMP="$TMP_PARENT/worktree"
cleanup() {
  git worktree remove --force "$TMP" >/dev/null 2>&1 || true
  rm -rf "$TMP_PARENT" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

echo "=== PRÉ-VALIDAÇÃO ISOLADA ==="
git worktree add --quiet --detach "$TMP" "$TARGET_SHA" || fail "não foi possível criar o worktree isolado de pré-validação."
cd "$TMP"

command -v node >/dev/null 2>&1 || fail "Node.js não encontrado."
run_limited node --check app/static/feature-loader.js || fail "feature-loader.js falhou na validação de sintaxe."

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3 || true)"
[[ -n "$PYTHON" ]] || fail "Python não encontrado."

export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
run_limited "$PYTHON" -m pytest -q tests/test_post_login_game_lazy_boot.py --disable-warnings --maxfail=1 || fail "regressão detectada no boot lazy do jogo."

cd "$ROOT"
AVAILABLE_KB="$(mem_available_kb)"
if [[ -z "$AVAILABLE_KB" || "$AVAILABLE_KB" -lt "$MIN_AVAILABLE_KB" ]]; then
  fail "RAM caiu abaixo do limite após a validação; atualização não será aplicada."
fi

[[ -z "$(git status --porcelain)" ]] || fail "checkout mudou durante a validação; atualização abortada."
[[ "$(git rev-parse HEAD)" == "$CURRENT_SHA" ]] || fail "HEAD mudou durante a validação; atualização abortada."

echo "=== APLICANDO SOMENTE APÓS TESTES ==="
git merge --ff-only "$TARGET" || fail "fast-forward falhou; checkout não foi alterado com merge parcial."

echo "=== RESULTADO ==="
echo "OK: atualização pré-validada e aplicada em $(git rev-parse --short HEAD)."
