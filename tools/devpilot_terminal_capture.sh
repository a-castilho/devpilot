#!/usr/bin/env bash

# DevPilot telemetry hook.
# Capture is opt-in and only installs when an explicit telemetry access token is
# available. Bootstrap credentials are never used for normal telemetry routes.

if [[ "${DEVPILOT_TERMINAL_CAPTURE:-0}" != "1" || -z "${DEVPILOT_TELEMETRY_TOKEN:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi

if [[ -n "${_DEVPILOT_CAPTURE_HOOK_INSTALLED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
export _DEVPILOT_CAPTURE_HOOK_INSTALLED=1

: "${DEVPILOT_HOME:=$HOME/Documents/devpilot}"
: "${DEVPILOT_URL:=http://127.0.0.1:8080}"
export DEVPILOT_HOME DEVPILOT_URL

_DEVPILOT_CAPTURE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_DEVPILOT_CAPTURE_HELPER="${_DEVPILOT_CAPTURE_DIR}/devpilot_terminal_capture.py"
_DEVPILOT_CAPTURE_LAST_COMMAND=""

__devpilot_capture_prompt() {
  local last_status=$?
  local command_text
  local capture_pid

  if [[ "${DEVPILOT_TERMINAL_CAPTURE:-0}" != "1" || -z "${DEVPILOT_TELEMETRY_TOKEN:-}" ]]; then
    return "$last_status"
  fi

  command_text="$(HISTTIMEFORMAT= history 1 2>/dev/null | sed -E 's/^[[:space:]]*[0-9]+[[:space:]]+//')"
  if [[ -z "$command_text" || "$command_text" == "$_DEVPILOT_CAPTURE_LAST_COMMAND" ]]; then
    return "$last_status"
  fi
  _DEVPILOT_CAPTURE_LAST_COMMAND="$command_text"

  case "$command_text" in
    *devpilot_terminal_capture*|*__devpilot_capture_prompt*)
      return "$last_status"
      ;;
  esac

  if [[ -f "$_DEVPILOT_CAPTURE_HELPER" ]]; then
    DEVPILOT_CAPTURE_COMMAND="$command_text" \
    DEVPILOT_CAPTURE_CWD="$PWD" \
    DEVPILOT_CAPTURE_SHELL="${SHELL##*/}" \
    DEVPILOT_CAPTURE_EXIT_CODE="$last_status" \
      command python3 "$_DEVPILOT_CAPTURE_HELPER" </dev/null >/dev/null 2>&1 &
    capture_pid=$!

    # This helper is fire-and-forget telemetry. Remove it from Bash job control
    # immediately so interactive shells never print "[n]+ Done/Exit ..." for it.
    disown "$capture_pid" 2>/dev/null || true
  fi
  return "$last_status"
}

case ";${PROMPT_COMMAND:-};" in
  *";__devpilot_capture_prompt;"*) ;;
  *) PROMPT_COMMAND="__devpilot_capture_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
esac

unset _DEVPILOT_CAPTURE_DIR
