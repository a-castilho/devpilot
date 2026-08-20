#!/usr/bin/env bash

# DevPilot telemetry hook.
# Source this file in an interactive Bash shell. It does not replace shell history,
# and it only sends commands while the server reports an active telemetry session.

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
      command python3 "$_DEVPILOT_CAPTURE_HELPER" >/dev/null 2>&1 &
  fi
  return "$last_status"
}

case ";${PROMPT_COMMAND:-};" in
  *";__devpilot_capture_prompt;"*) ;;
  *) PROMPT_COMMAND="__devpilot_capture_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}" ;;
esac

unset _DEVPILOT_CAPTURE_DIR
