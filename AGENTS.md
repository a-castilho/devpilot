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
- Load optional UI/domain modules only after explicit user intent through `feature-loader.js`.
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

## Cloud platform standard

- Every DevPilot-created full-stack project must use the platform topology `Vercel -> Render -> Neon` by default.
- Vercel is the primary public frontend and must be the URL shown to users when a frontend exists.
- Render hosts the backend/API and must remain capable of serving the application frontend as a fallback/backup whenever the project supports a bundled frontend.
- Neon is the default managed PostgreSQL provider. Do not provision a new Render PostgreSQL database for DevPilot projects unless an explicit project exception requires it.
- Frontend traffic should reach the Render backend through a configured same-origin gateway or explicit API base URL; the Vercel deployment must not contain database credentials.
- Render receives the Neon `DATABASE_URL` through protected environment configuration; never commit connection strings or database passwords.
- Deployment state must keep the primary Vercel URL and the Render backup URL separately so the product can fail over or expose diagnostics without ambiguity.
- The delivery pipeline may omit a layer only when the project genuinely has no corresponding component, but new full-stack projects must default to all three providers.
- DevPilot itself follows the same topology in homologation and production.

## Validation

- Run `pytest` for backend changes.
- Run `python -m compileall app` after Python changes.
- Run `python scripts/check-engineering-standards.py --changed` for every change.
- Run `python scripts/critical-quality-matrix.py` to validate critical-module ownership and test contracts.
- Verify the responsive dashboard manually after visible UI changes.
- Review the final diff for secrets, unsafe subprocess use, missing authorization, unrelated edits, hidden loaders, and boot-cost regressions.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

