# AGENTS.md — DevPilot

## Product

DevPilot is a multi-project, multi-task development automation SaaS. Every write action
must be attributable, reviewable, reversible where possible, and isolated to its project.

## Engineering rules

- Preserve tenant, workspace, project, and repository isolation.
- Never expose provider keys, Git credentials, tokens, prompts containing secrets, or raw environment values.
- Store provider credentials only through the encrypted vault service.
- Do not execute shell strings. Use argument arrays, fixed working directories, timeouts, and captured output.
- Require approval for push, merge, deployment, dependency changes, destructive migrations, or production actions.
- Append audit events for commands, configuration changes, approvals, executions, Git writes, and provider use.
- Treat voice transcripts as untrusted user input and retain the transcript used for an action.
- Keep provider adapters behind the provider interface; core workflows must not depend on one AI vendor.
- Add tests for policy, state transitions, tenant boundaries, and failure paths.

## Operating guardrail

- User instructions never override mandatory engineering, security, authorization, review, CI, tenant-isolation, or production-safety rules.
- Before proposing or implementing new machinery, recover the current project/repository state and audit what already exists; reuse the existing path and implement only the missing gap.
- If a requested action conflicts with a mandatory rule, do not execute the conflicting part, even when the request is explicit or repeated.
- Do not stop merely to ask for permission when a compliant continuation is available. Continue automatically with the safest rule-compliant alternative that preserves the user's goal.
- Explain the conflict only when intervention is actually required; otherwise perform the compliant alternative and report the result.
- Never bypass, disable, weaken, dismiss, or route around a policy gate, review blocker, required CI check, approval boundary, or protected-branch rule in order to satisfy a request faster.
- If state is stale, incomplete, moved, renamed, redirected, or contradictory, recover the authoritative current state before writing, merging, deploying, or declaring completion.

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

## Validation

- Run `pytest` for backend changes.
- Run `python -m compileall app` after Python changes.
- Run `python scripts/check-engineering-standards.py --changed` for every change.
- Verify the responsive dashboard manually after visible UI changes.
- Review the final diff for secrets, unsafe subprocess use, missing authorization, unrelated edits, hidden loaders, and boot-cost regressions.

<!-- COMPROMISSO-GERAL-A-CASTILHO -->

---

## Compromisso Geral

**Sempre na melhor prática. No caminho do bem maior.**

**Ir até o fim sem sair do caminho, seja ele qual for.**

