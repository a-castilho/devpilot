#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${PYTHON_BIN:-}" ]]; then
  PYTHON_CMD="$PYTHON_BIN"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON_CMD=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python)"
else
  echo "Erro: Python não encontrado. Ative o .venv ou instale Python 3.12+." >&2
  exit 127
fi

"$PYTHON_CMD" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit(
        f"Erro: DevPilot requer Python 3.12+, encontrado {sys.version.split()[0]} em {sys.executable}"
    )
print(f"Python: {sys.executable} ({sys.version.split()[0]})")
PY

"$PYTHON_CMD" -m compileall -q app
"$PYTHON_CMD" scripts/check-engineering-standards.py --changed

node --check app/static/app.js
node --check app/static/auth-ui.js
node --check app/static/acs-loader.js
node --check app/static/feature-loader.js
node --check app/static/task-modal.js
node --check app/static/task-image-upload.js
node --check app/static/analysis-failure-actions.js
node --check app/static/repeatai-pattern-graphs.js
node --check app/static/mobile-project-card-compact.js
node --check app/static/reports.js
node --check app/static/project-provisioning.js
node --check app/static/provider-models.js
node --check app/static/super-admin-voice.js
node --check app/static/super-admin-system-map.js
node --check app/static/voice-project-start.js
node --check app/static/voice-chatgpt-layout.js
node --check app/static/voice-local-update.js
node --check app/static/voice-insecure-lan-guard.js
node --check app/static/tasks-lazy-load.js
node --check app/static/telemetry-replay-capture.js
node --check app/static/telemetry-replay.js
node --check app/static/linux-terminal.js
node --check app/static/linux-beginner-coach.js
node --check app/static/linux-git-cloud.js
node --check app/static/audit-integrity.js
node --check app/static/token-usage.js
node --check app/static/token-usage-mobile-fix.js
node --check app/static/investia-admin.js
node --check app/static/system-tests.js
node --check app/static/mission-control.js
node --check app/static/build-game.js
node --check app/static/build-game-subphases.js
node --check app/static/build-game-url-bonus.js
bash -n scripts/install-linux-agent.sh
bash -n scripts/devpilot-local-safe.sh

"$PYTHON_CMD" -m json.tool vercel.json >/dev/null
node --check tools/build-vercel-static.mjs
node tools/build-vercel-static.mjs

test -f .vercel-static/index.html
test -f .vercel-static/assets/app.js
test -f .vercel-static/assets/auth-ui.js
test -f .vercel-static/assets/task-image-upload.js
test -f .vercel-static/assets/analysis-failure-actions.js
test -f .vercel-static/assets/repeatai-pattern-graphs.js
test -f .vercel-static/assets/mobile-project-card-compact.js
test -f .vercel-static/assets/linux-terminal.js
test -f .vercel-static/assets/linux-git-cloud.js
test -f .vercel-static/assets/audit-integrity.js
test -f .vercel-static/assets/token-usage.js
test -f .vercel-static/assets/token-usage-mobile-fix.js
test -f .vercel-static/assets/system-tests.js
test -f .vercel-static/assets/mission-control.js
test -f .vercel-static/assets/mission-control.css
test -f .vercel-static/assets/build-game.js
test -f .vercel-static/assets/build-game-subphases.js
test -f .vercel-static/assets/build-game-url-bonus.js
test -f .vercel-static/assets/super-admin-voice.js
test -f .vercel-static/assets/super-admin-system-map.js
test -f .vercel-static/assets/super-admin-system-map.css
grep -q '/assets/mission-control.js' .vercel-static/index.html
grep -q '/assets/super-admin-voice.js' .vercel-static/index.html

"$PYTHON_CMD" -m pytest
