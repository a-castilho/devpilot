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
alias atualizar-local='bash ~/Documents/devpilot/scripts/atualizar-local.sh'
alias atualizar='bash ~/Documents/devpilot/scripts/atualizar-local.sh'
alias reconstruir-sistema='bash ~/Documents/devpilot/scripts/reconstruir-sistema.sh'
alias reconstruir='bash ~/Documents/devpilot/scripts/reconstruir-sistema.sh'
# <<< DEVPILOT ALIASES <<<
EOF

cat "$TMP" > "$RC_FILE"
rm -f "$TMP"

echo "Aliases instalados:"
echo "  atualizar-local"
echo "  atualizar"
echo "  reconstruir-sistema"
echo "  reconstruir"
echo
echo "Execute: source ~/.bashrc"
