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
# Use shell functions instead of aliases so the commands also work immediately
# after `source ~/.bashrc` inside the same compound shell command.
atualizar-local() { bash "$HOME/Documents/devpilot/scripts/atualizar-local.sh" "$@"; }
atualizar() { atualizar-local "$@"; }
reconstruir-sistema() { bash "$HOME/Documents/devpilot/scripts/reconstruir-sistema.sh" "$@"; }
reconstruir() { reconstruir-sistema "$@"; }
# <<< DEVPILOT ALIASES <<<
EOF

cat "$TMP" > "$RC_FILE"
rm -f "$TMP"

chmod +x \
  "$HOME/Documents/devpilot/scripts/atualizar-local.sh" \
  "$HOME/Documents/devpilot/scripts/reconstruir-sistema.sh" 2>/dev/null || true

echo "Comandos instalados:"
echo "  atualizar-local"
echo "  atualizar"
echo "  reconstruir-sistema"
echo "  reconstruir"
echo
echo "Execute: source ~/.bashrc"
