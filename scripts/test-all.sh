#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RESULT_DIR="${DEVPILOT_TEST_RESULTS_DIR:-.artifacts/test-results}"
export DEVPILOT_TEST_RESULTS_DIR="$RESULT_DIR"
mkdir -p "$RESULT_DIR"
rm -f "$RESULT_DIR"/*.log "$RESULT_DIR"/*.xml "$RESULT_DIR"/*.json "$RESULT_DIR"/summary.txt "$RESULT_DIR"/*.png

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_CMD="$PYTHON_BIN"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON_CMD=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python)"
else
  echo "Erro: Python não encontrado." >&2
  exit 127
fi

failures=0

record() {
  local name="$1"
  local rc="$2"
  if [[ "$rc" -eq 0 ]]; then
    printf 'PASS  %s\n' "$name" | tee -a "$RESULT_DIR/summary.txt"
  else
    printf 'FAIL  %s (exit=%s)\n' "$name" "$rc" | tee -a "$RESULT_DIR/summary.txt"
    failures=$((failures + 1))
  fi
}

run_logged() {
  local name="$1"
  shift
  local log="$RESULT_DIR/${name}.log"
  echo
  echo "=== ${name} ==="
  "$@" 2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  record "$name" "$rc"
  return 0
}

run_logged python-version "$PYTHON_CMD" -c 'import sys; print(sys.executable, sys.version); raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'
run_logged python-compile "$PYTHON_CMD" -m compileall -q app
run_logged engineering-standards "$PYTHON_CMD" scripts/check-engineering-standards.py --changed
run_logged nonblocking-recovery-focused "$PYTHON_CMD" -m pytest -q tests/test_recovery.py tests/test_failure_recovery_flow_contract.py tests/test_nonblocking_recovery_worker_contract.py tests/test_automation_first_recovery_no_block.py

matrix_args=(
  scripts/critical-quality-matrix.py
  --report "$RESULT_DIR/critical-quality-matrix.json"
)
if [[ "${DEVPILOT_RUN_CRITICAL_MATRIX:-0}" == "1" ]]; then
  matrix_args+=(--run)
fi
if [[ -n "${DEVPILOT_POLICY_BASE:-}" ]]; then
  matrix_args+=(--base "$DEVPILOT_POLICY_BASE")
fi
run_logged critical-quality-matrix "$PYTHON_CMD" "${matrix_args[@]}"

run_logged javascript bash -c '
  set -o pipefail
  if ! command -v node >/dev/null 2>&1; then
    echo "Node.js não encontrado" >&2
    exit 127
  fi
  rc=0
  while IFS= read -r -d "" file; do
    echo "node --check $file"
    node --check "$file" || rc=1
  done < <(find app/static tools -type f \( -name "*.js" -o -name "*.mjs" \) -print0 | sort -z)
  exit "$rc"
'

run_logged shell-syntax bash -c '
  rc=0
  while IFS= read -r -d "" file; do
    echo "bash -n $file"
    bash -n "$file" || rc=1
  done < <(find scripts -maxdepth 1 -type f -name "*.sh" -print0 | sort -z)
  exit "$rc"
'

run_logged vercel-json "$PYTHON_CMD" -m json.tool vercel.json
run_logged vercel-build node tools/build-vercel-static.mjs

run_logged vercel-assets bash -c '
  required=(
    .vercel-static/index.html
    .vercel-static/assets/app.js
    .vercel-static/assets/auth-ui.js
    .vercel-static/assets/feature-loader.js
    .vercel-static/assets/build-game.js
    .vercel-static/assets/game-shell.js
    .vercel-static/assets/super-admin-voice.js
  )
  rc=0
  for file in "${required[@]}"; do
    if [[ -f "$file" ]]; then
      echo "OK $file"
    else
      echo "FALTA $file" >&2
      rc=1
    fi
  done
  exit "$rc"
'

# Pytest de unidade/integração roda inteiro e exclui o browser gate, que possui
# uma etapa própria para manter diagnóstico e artifacts separados.
echo
echo "=== pytest-all ==="
"$PYTHON_CMD" -m pytest -q -m "not browser_e2e" --disable-warnings --junitxml="$RESULT_DIR/pytest.xml" 2>&1 | tee "$RESULT_DIR/pytest.log"
pytest_rc=${PIPESTATUS[0]}
record pytest-all "$pytest_rc"

if [[ "${DEVPILOT_RUN_BROWSER_E2E:-0}" == "1" ]]; then
  echo
  echo "=== browser-e2e ==="

  # Colete somente módulos E2E. Apontar pytest para tests/ inteiro faz a coleta
  # importar testes unitários e módulos de aplicação antes do fixture E2E instalar
  # o ambiente isolado, podendo reutilizar settings/engine do processo incorretos.
  mapfile -d '' -t browser_e2e_files < <(
    find tests -maxdepth 1 -type f -name '*_browser_e2e.py' -print0 | sort -z
  )

  if [[ "${#browser_e2e_files[@]}" -eq 0 ]]; then
    echo "Nenhum arquivo *_browser_e2e.py encontrado; browser gate não pode ficar vazio." >&2
    record browser-e2e 1
  else
    echo "Arquivos E2E selecionados:"
    printf '  - %s\n' "${browser_e2e_files[@]}"
    "$PYTHON_CMD" -m pytest -q -m browser_e2e "${browser_e2e_files[@]}" \
      --disable-warnings --junitxml="$RESULT_DIR/browser-e2e.xml" \
      2>&1 | tee "$RESULT_DIR/browser-e2e.log"
    browser_rc=${PIPESTATUS[0]}
    record browser-e2e "$browser_rc"
  fi
else
  echo
  echo "=== browser-e2e ==="
  echo "SKIP local: defina DEVPILOT_RUN_BROWSER_E2E=1 para executar os E2E de navegador."
  printf 'SKIP  browser-e2e (opt-in local; obrigatório no CI)\n' | tee -a "$RESULT_DIR/summary.txt"
fi

{
  echo
  echo "=== RESULTADO AGREGADO ==="
  cat "$RESULT_DIR/summary.txt"
  echo
  if [[ "$failures" -eq 0 ]]; then
    echo "TODAS AS VALIDAÇÕES PASSARAM"
  else
    echo "$failures etapa(s) falharam. Consulte $RESULT_DIR"
  fi
} | tee "$RESULT_DIR/final.log"

exit "$failures"
