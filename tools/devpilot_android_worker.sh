#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT="${DEVPILOT_PROJECT:-$HOME/Documents/devpilot}"
REMOTE="${DEVPILOT_ANDROID_WORKER_HOST:-celular-worker}"
THRESHOLD_MB="${DEVPILOT_REMOTE_THRESHOLD_MB:-1200}"
REMOTE_MIN_MB="${DEVPILOT_ANDROID_REMOTE_MIN_MB:-600}"
REMOTE_ROOT="${DEVPILOT_ANDROID_REMOTE_ROOT:-projects}"

PROJECT="$(realpath "$PROJECT")"
PROJECT_NAME="$(basename "$PROJECT")"
REMOTE_PROJECT="~/$REMOTE_ROOT/$PROJECT_NAME"

local_memory() {
    awk '/MemAvailable:/ {printf "%d", $2 / 1024}' /proc/meminfo
}

remote_online() {
    ssh -o BatchMode=yes -o ConnectTimeout=4 "$REMOTE" 'exit 0' >/dev/null 2>&1
}

remote_memory() {
    ssh -o BatchMode=yes -o ConnectTimeout=4 "$REMOTE" \
        "awk '/MemAvailable:/ {printf \"%d\", \$2 / 1024}' /proc/meminfo \
        2>/dev/null || echo 0
}

safe_remote_command() {
    local command="$1"
    printf '%s' "$command" | grep -Eqi \
        '^(python3? -m compileall|python3? -m pytest|pytest([[:space:]]|$)|npm test([[:space:]]|$)|npm run test([[:space:]]|$)|npm run build([[:space:]]|$)|node[[:space:]])'
}

host_only_command() {
    local command="$1"
    printf '%s' "$command" | grep -Eqi \
        '(^|[[:space:]])(docker|docker-compose|systemctl|sudo|apt|snap|mount|umount|nmcli|ufw|codex)([[:space:]]|$)'
}

sync_project() {
    remote_online || return 1
    ssh "$REMOTE" "mkdir -p $REMOTE_PROJECT"
    rsync -az --delete \
        --include='/.env.example' \
        --exclude='/.env' \
        --exclude='/.env.*' \
        --exclude='*.pem' \
        --exclude='*.key' \
        --exclude='*.secret' \
        --exclude='secrets/' \
        --exclude='.venv/' \
        --exclude='venv/' \
        --exclude='node_modules/' \
        --exclude='__pycache__/' \
        --exclude='.pytest_cache/' \
        --exclude='data/' \
        --exclude='runtime/' \
        --exclude='*.log' \
        "$PROJECT/" "$REMOTE:$REMOTE_ROOT/$PROJECT_NAME/"
}

run_local() {
    local command="$1"
    echo "EXECUTOR=NOTEBOOK"
    echo "COMMAND=$command"
    cd "$PROJECT"
    bash -lc "$command"
}

run_remote() {
    local command="$1"
    local quoted
    safe_remote_command "$command" || {
        echo "resource_command_not_allowed" >&2
        return 64
    }
    sync_project
    printf -v quoted '%q' "$command"
    echo "EXECUTOR=ANDROID"
    echo "COMMAND=$command"
    ssh "$REMOTE" "cd $REMOTE_PROJECT && bash -lc $quoted"
}

status() {
    local local_mb remote_mb state decision
    local_mb="$(local_memory)"
    if remote_online; then
        remote_mb="$(remote_memory)"
        state="ONLINE"
    else
        remote_mb=0
        state="OFFLINE"
    fi
    decision="NOTEBOOK"
    if [ "$local_mb" -lt "$THRESHOLD_MB" ] && [ "$remote_mb" -gt "$REMOTE_MIN_MB" ]; then
        decision="ANDROID"
    fi
    printf 'NOTEBOOK_AVAILABLE_MB=%s\n' "$local_mb"
    printf 'ANDROID_AVAILABLE_MB=%s\n' "$remote_mb"
    printf 'ANDROID_STATE=%s\n' "$state"
    printf 'THRESHOLD_MB=%s\n' "$THRESHOLD_MB"
    printf 'DECISION=%s\n' "$decision"
}

MODE="${1:-status}"
shift || true
COMMAND="$*"

case "$MODE" in
    status)
        status
        ;;
    local)
        [ -n "$COMMAND" ] || { echo "command_required" >&2; exit 2; }
        run_local "$COMMAND"
        ;;
    remote)
        [ -n "$COMMAND" ] || { echo "command_required" >&2; exit 2; }
        remote_online || { echo "android_worker_offline" >&2; exit 3; }
        run_remote "$COMMAND"
        ;;
    auto)
        [ -n "$COMMAND" ] || { echo "command_required" >&2; exit 2; }
        if host_only_command "$COMMAND"; then
            echo "ROUTE=NOTEBOOK reason=host_only"
            run_local "$COMMAND"
            exit $?
        fi
        if ! safe_remote_command "$COMMAND"; then
            echo "ROUTE=NOTEBOOK reason=not_android_allowlisted"
            run_local "$COMMAND"
            exit $?
        fi

        LOCAL_MB="$(local_memory)"
        REMOTE_MB=0
        if remote_online; then
            REMOTE_MB="$(remote_memory)"
        fi

        echo "NOTEBOOK_AVAILABLE_MB=$LOCAL_MB"
        echo "ANDROID_AVAILABLE_MB=$REMOTE_MB"
        echo "THRESHOLD_MB=$THRESHOLD_MB"

        if [ "$LOCAL_MB" -lt "$THRESHOLD_MB" ] && [ "$REMOTE_MB" -gt "$REMOTE_MIN_MB" ]; then
            echo "ROUTE=ANDROID reason=memory_pressure"
            if run_remote "$COMMAND"; then
                exit 0
            fi
            echo "ROUTE=NOTEBOOK reason=android_failed_fallback"
        else
            echo "ROUTE=NOTEBOOK reason=resources_ok_or_android_unavailable"
        fi
        run_local "$COMMAND"
        ;;
    *)
        echo "usage: devpilot_android_worker.sh {status|auto|local|remote} [command]" >&2
        exit 2
        ;;
esac
