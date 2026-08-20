#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${DEVPILOT_ROOT:-$HOME/Documents/devpilot}"
BRANCH="${DEVPILOT_UPDATE_BRANCH:-main}"
HEALTH_URL="${DEVPILOT_HEALTH_URL:-http://127.0.0.1:8080/health}"
RUNTIME_DIR="${DEVPILOT_RUNTIME_DIR:-$ROOT/runtime}"
LOG_DIR="$RUNTIME_DIR/logs"
LOCK_FILE="$RUNTIME_DIR/local-update.lock"
mkdir -p "$LOG_DIR" "$RUNTIME_DIR"
LOG_FILE="$LOG_DIR/local-update-$(date +%Y%m%d).log"

exec > >(tee -a "$LOG_FILE") 2>&1
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date -Is)] UPDATE_LOCAL=IGNORED reason=already_running"
  exit 0
fi

fail() {
  echo "[$(date -Is)] UPDATE_LOCAL=FAILED reason=$*"
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git_not_found"
[ -d "$ROOT/.git" ] || fail "repository_not_found root=$ROOT"
cd "$ROOT"

CURRENT_BRANCH="$(git branch --show-current)"
[ "$CURRENT_BRANCH" = "$BRANCH" ] || fail "unexpected_branch current=$CURRENT_BRANCH expected=$BRANCH"

if ! git diff --quiet || ! git diff --cached --quiet; then
  fail "tracked_local_changes_present"
fi

BEFORE="$(git rev-parse --short HEAD)"
echo "[$(date -Is)] UPDATE_LOCAL=START branch=$BRANCH head=$BEFORE"

git fetch --prune origin "$BRANCH"
REMOTE="$(git rev-parse "origin/$BRANCH")"
LOCAL="$(git rev-parse HEAD)"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[$(date -Is)] GIT=ALREADY_CURRENT head=$BEFORE"
  echo "[$(date -Is)] UPDATE_LOCAL=OK changed=false"
  exit 0
fi

git merge --ff-only "origin/$BRANCH"
AFTER="$(git rev-parse --short HEAD)"
echo "[$(date -Is)] GIT=UPDATED before=$BEFORE after=$AFTER"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  export COMPOSE_PARALLEL_LIMIT="${COMPOSE_PARALLEL_LIMIT:-1}"
  echo "[$(date -Is)] DOCKER=BUILD parallel_limit=$COMPOSE_PARALLEL_LIMIT"
  docker compose build app worker
  echo "[$(date -Is)] DOCKER=RECREATE"
  docker compose up -d --force-recreate app worker

  echo "[$(date -Is)] HEALTH=WAIT url=$HEALTH_URL"
  HEALTH_OK=0
  for _ in $(seq 1 30); do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      HEALTH_OK=1
      break
    fi
    sleep 1
  done
  [ "$HEALTH_OK" -eq 1 ] || fail "health_check_failed url=$HEALTH_URL"
  echo "[$(date -Is)] HEALTH=OK"
else
  echo "[$(date -Is)] DOCKER=SKIPPED reason=docker_compose_unavailable"
fi

echo "[$(date -Is)] UPDATE_LOCAL=OK changed=true head=$AFTER"
