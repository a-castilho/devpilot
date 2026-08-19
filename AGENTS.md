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

## AgentOS architecture rules

- Treat `app/agentos` as a bounded context with inward-pointing dependencies.
- Keep `app/agentos/domain` free of FastAPI, SQLAlchemy, HTTP clients and provider SDKs.
- Put orchestration use cases in `app/agentos/application`; depend on small ports/protocols rather than concrete infrastructure.
- Put SQLAlchemy, Ollama, audit and external-tool integrations in infrastructure adapters.
- Wire concrete dependencies only in `app/agentos/container.py`; routes and MCP handlers consume use cases.
- Prefer Strategy/Factory for replaceable planning/model behavior and Repository/Unit of Work for persistence boundaries.
- Publish cross-cutting side effects as domain events when practical; keep the local profile in-process until a broker is justified.
- Preserve the modular-monolith deployment for the 4 GB development profile; extract services only when independent scaling is measurable.

## Validation

- Run `pytest` for backend changes.
- Run `python -m compileall app` after Python changes.
- Verify the responsive dashboard manually after visible UI changes.
- Review the final diff for secrets, unsafe subprocess use, missing authorization, and unrelated edits.
