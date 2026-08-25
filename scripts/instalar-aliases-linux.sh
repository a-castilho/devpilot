#!/usr/bin/env bash
set -euo pipefail

RC_FILE="${HOME}/.bashrc"
START="# >>> DEVPILOT ALIASES >>>"
END="# <<< DEVPILOT ALIASES <<<"
TMP="$(mktemp)"

if [ -f "$RC_FILE" ]; then
  awk -v start="$START" -v end="$END" '
    $0 == start {skip=1; next}
    $0 == end {skip=0; next}
    !skip {print}
  ' "$RC_FILE" > "$TMP"
else
  : > "$TMP"
fi

cat >> "$TMP" <<'EOF'
# >>> DEVPILOT ALIASES >>>
export DEVPILOT_HOME="$HOME/Documents/devpilot"
export DEVPILOT_URL="http://127.0.0.1:8080"
export DEVPILOT_TERMINAL_CAPTURE="${DEVPILOT_TERMINAL_CAPTURE:-0}"

# Funções em vez de aliases: funcionam também depois de `source ~/.bashrc`.
atualizar-local() {
  bash "$DEVPILOT_HOME/scripts/atualizar-local.sh" "$@"
  local rc=$?
  if [ "$rc" -eq 0 ] && \
     [ "${DEVPILOT_TERMINAL_CAPTURE:-0}" = "1" ] && \
     [ -n "${DEVPILOT_TELEMETRY_TOKEN:-}" ] && \
     [ -f "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh" ]; then
    source "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh"
  fi
  return "$rc"
}
atualizar() { atualizar-local "$@"; }
reconstruir-sistema() { bash "$DEVPILOT_HOME/scripts/reconstruir-sistema.sh" "$@"; }
reconstruir() { reconstruir-sistema "$@"; }

# Captura de terminal é opt-in. Para habilitar, forneça explicitamente um token
# de acesso válido para telemetria; nunca reutilize DEVPILOT_BOOTSTRAP_TOKEN.
if [[ $- == *i* ]] && \
   [ "${DEVPILOT_TERMINAL_CAPTURE:-0}" = "1" ] && \
   [ -n "${DEVPILOT_TELEMETRY_TOKEN:-}" ] && \
   [ -f "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh" ]; then
  source "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh"
fi
# <<< DEVPILOT ALIASES <<<
EOF

cat "$TMP" > "$RC_FILE"
rm -f "$TMP"

chmod +x \
  "$HOME/Documents/devpilot/scripts/atualizar-local.sh" \
  "$HOME/Documents/devpilot/scripts/reconstruir-sistema.sh" \
  "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh" \
  "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.py" 2>/dev/null || true

echo "Comandos instalados:"
echo "  atualizar-local"
echo "  atualizar"
echo "  reconstruir-sistema"
echo "  reconstruir"
echo
echo "Telemetria de terminal: desabilitada por padrão em 127.0.0.1:8080"
echo "Habilite apenas com DEVPILOT_TERMINAL_CAPTURE=1 e DEVPILOT_TELEMETRY_TOKEN válido."
echo "Execute agora: source ~/.bashrc"
