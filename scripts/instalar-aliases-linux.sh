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

# Funções em vez de aliases: funcionam também depois de `source ~/.bashrc`.
subir-projeto() { bash "$DEVPILOT_HOME/scripts/subir-projeto.sh" "$@"; }
subir() { subir-projeto "$@"; }
atualizar-local() {
  bash "$DEVPILOT_HOME/scripts/atualizar-local.sh" "$@"
  local rc=$?
  if [ "$rc" -eq 0 ] && [ -f "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh" ]; then
    source "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh"
  fi
  return "$rc"
}
atualizar() { atualizar-local "$@"; }
reconstruir-sistema() { bash "$DEVPILOT_HOME/scripts/reconstruir-sistema.sh" "$@"; }
reconstruir() { reconstruir-sistema "$@"; }

# O hook só envia comandos quando há uma sessão de telemetria ativa.
# O helper lê o token localmente do ambiente/.env sem imprimi-lo no terminal.
if [[ $- == *i* ]] && [ -f "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh" ]; then
  source "$DEVPILOT_HOME/tools/devpilot_terminal_capture.sh"
fi
# <<< DEVPILOT ALIASES <<<
EOF

cat "$TMP" > "$RC_FILE"
rm -f "$TMP"

chmod +x \
  "$HOME/Documents/devpilot/scripts/subir-projeto.sh" \
  "$HOME/Documents/devpilot/scripts/atualizar-local.sh" \
  "$HOME/Documents/devpilot/scripts/reconstruir-sistema.sh" \
  "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.sh" \
  "$HOME/Documents/devpilot/tools/devpilot_terminal_capture.py" 2>/dev/null || true

echo "Comandos instalados:"
echo "  subir-projeto"
echo "  subir"
echo "  atualizar-local"
echo "  atualizar"
echo "  reconstruir-sistema"
echo "  reconstruir"
echo
echo "Telemetria de terminal: auto-carregamento Bash configurado em 127.0.0.1:8080"
echo "Execute agora: source ~/.bashrc"
