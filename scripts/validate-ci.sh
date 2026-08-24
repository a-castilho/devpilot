#!/usr/bin/env bash
set -euo pipefail

python -m compileall -q app

node --check app/static/app.js
node --check app/static/task-modal.js
node --check app/static/task-image-upload.js
node --check app/static/analysis-failure-actions.js
node --check app/static/repeatai-pattern-graphs.js
node --check app/static/mobile-project-card-compact.js
node --check app/static/reports.js
node --check app/static/project-provisioning.js
node --check app/static/provider-models.js
node --check app/static/voice-project-start.js
node --check app/static/voice-local-update.js
node --check app/static/voice-insecure-lan-guard.js
node --check app/static/tasks-lazy-load.js
node --check app/static/telemetry-replay-capture.js
node --check app/static/telemetry-replay.js
node --check app/static/linux-terminal.js
node --check app/static/token-usage.js
node --check app/static/token-usage-mobile-fix.js
node --check app/static/investia-admin.js
node --check app/static/system-tests.js
bash -n scripts/install-linux-agent.sh

python -m json.tool vercel.json >/dev/null
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
test -f .vercel-static/assets/token-usage.js
test -f .vercel-static/assets/token-usage-mobile-fix.js
test -f .vercel-static/assets/system-tests.js

pytest
