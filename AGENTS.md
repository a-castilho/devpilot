# AGENTS.md — DevPilot

## Product

DevPilot is a multi-project, multi-task development automation SaaS. Every write action
must be attributable, reviewable, reversible where possible, and isolated to its project.

## Engineering rules

- Preserve tenant, workspace, project, and repository isolation.
- Never expose provider keys, Git credentials, tokens, prompts containing secrets, or raw environment values.
- Store provider credentials only through the encrypted vault service.
- Do not execute shell strings. Use argument arrays, fixed working directories, timeouts, and captured output.
- Treat safe, local, auditable, and reversible actions as pre-authorized. Do not stop for per-step approval when analyzing, editing code, creating files, running tests/lint/build, creating local branches, or creating local commits.
- Require approval for push, merge, deployment, dependency changes, destructive migrations, destructive data/filesystem operations, credential/secret changes, or production actions.
- Append audit events for commands, configuration changes, approvals, executions, Git writes, and provider use.
- Treat voice transcripts as untrusted user input and retain the transcript used for an action.
- Keep provider adapters behind the provider interface; core workflows must not depend on one AI vendor.
- Add tests for policy, state transitions, tenant boundaries, and failure paths.

## Local runtime safety

- Never instruct a user to restart DevPilot with a raw `pkill -f` sequence followed by `nohup`.
- Use `bash scripts/devpilot-local-safe.sh` for local update/restart workflows.
- Validate the new revision before stopping a healthy local process.
- Refuse destructive update/restart when the worktree has uncommitted changes.
- After restart, require `/health` to succeed; if a newly pulled revision fails to boot, restore the previous revision automatically when possible.
- Keep the user-facing recovery command short and avoid chaining unrelated tests before service recovery.

## Reliability and regression prevention standard

- Keep pre-authentication limited to `acs-loader.js` and `auth-ui.js`.
- Keep the automatic authenticated core exactly `app.js` plus `feature-loader.js`.
- `app/static/runtime-manifest.js` is the single source of truth for frontend feature bundles, critical assets, navigation triggers, load policies, and standalone routes.
- Do not duplicate feature inventories or navigation-trigger maps in `feature-loader.js`, `app/main.py`, ordinary frontend modules, tests, or documentation. Consumers must read the runtime manifest instead.
- Any new frontend feature or dashboard must be registered in `runtime-manifest.js` and covered by `tests/test_frontend_runtime_manifest.py` before merge.
- The unified runtime contract must preserve the user dashboard, project ships, project delivery actions, Development actions, reports/graphs, voice/chat, Audit, and all Super Admin dashboards.
- Do not remove `project-ships.js`, `super-admin-task-panel.js`, `token-usage.js`, `cloud-admin.js`, `deploy-admin.js`, `mission-control.js`, `rag-admin-ui.js`, or `rag-jobs-ui.js` from the runtime contract without an explicit product decision and matching migration.
- Load optional UI/domain modules only after explicit user intent through `feature-loader.js`.
- Explicit feature loading must remain cooperative: load critical assets first, return control to the browser between scripts, then warm non-critical enhancements in background idle time.
- Do not add hidden dynamic script loaders to ordinary frontend modules.
- Do not add global `MutationObserver` instances to ordinary frontend modules; prefer explicit lifecycle/domain events.
- Never reintroduce an automatic post-login second wave through timers, idle callbacks, analytics modules, or legacy loaders.
- A regression that caused an incident must become an automated test or policy gate whenever technically viable.
- Treat a red `DevPilot policy` or `DevPilot quality` gate as a release blocker; do not remove or weaken the gate to make CI pass.
- Keep normal product changes off `main` until reviewed and validated; configure `main` to require Pull Request plus the policy and quality checks.
- For local runtime tests, verify that `/health` identifies the DevPilot service and that the expected PID, port, commit, and log belong to the process under test.
- Follow `docs/ENGINEERING_STANDARD.md` for the complete mandatory standard.

## Critical module quality matrix

- Keep `.devpilot/quality-modules.json` as the auditable source of truth that maps every critical domain to its source paths, focused tests, and browser E2E contracts.
- Keep authentication, tasks/worker, game, Super Admin, RAG, GitHub, Linux, cloud/deploy, and frontend represented in the matrix.
- A new or changed critical source path must belong to a declared module; guarded critical code without an owner is a policy failure.
- Every active critical module must resolve at least one automated focused test. Optional modules such as RAG become mandatory automatically as soon as their source exists.
- Structural changes to runtime, database, configuration, CI, Docker, deployment build, policy, or the matrix itself select every active module for the focused gate.
- CI must run the focused matrix before the complete suite; the complete suite remains mandatory and must not be replaced by selective testing.
- Browser E2E tests must use the `browser_e2e` pytest marker and the `*_browser_e2e.py` naming contract. CI collects only those files and then filters by marker so unit-test imports cannot contaminate the isolated browser runtime.
- Do not remove a path, module, test contract, guard, or browser E2E from the matrix merely to make CI pass; fix the implementation or update the contract to reflect the real architecture.

## Validation

- Run `pytest` for backend changes.
- Run `python -m compileall app` after Python changes.
- Run `python scripts/check-engineering-standards.py --changed` for every change.
- Run `python scripts/critical-quality-matrix.py` to validate critical-module ownership and test contracts.
- Run `pytest -q tests/test_frontend_runtime_manifest.py tests/test_authenticated_minimal_boot.py tests/test_project_visual_telemetry.py` after any frontend runtime or navigation change.
- Verify the responsive dashboard manually after visible UI changes.
- Review the final diff for secrets, unsafe subprocess use, missing authorization, unrelated edits, hidden loaders, and boot-cost regressions.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

