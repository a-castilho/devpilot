# Host actions — security boundary

Host actions cross the DevPilot application/container boundary and execute on the Linux host. They therefore use a closed set of named operations and must never carry a free-form shell command.

## Current contract

- The application-level queue helper accepts only explicitly allow-listed action names.
- The host runner maps each accepted action to a repository-owned script selected in code.
- Payload fields are data only; they cannot select an executable or inject shell syntax.
- Unknown and legacy actions fail closed and are moved to the failed queue.
- `manual_deploy` with a `command` field is intentionally disabled. Existing configuration can remain visible for migration/history, but it cannot be executed.

The current host runner accepts the named operations `update_local` and `pipeline_repair`. `update_local` is queued through `app.services.host_actions`; `pipeline_repair` has its own SUPER_ADMIN route and writes a fixed action payload.

## Reintroducing manual deploy safely

Do not restore `bash -lc`, `shell=True`, or any equivalent free-form command execution. A future manual deployment must use a structured adapter with a fixed provider/action contract, for example an approved Vercel, Render, or other deployment adapter that validates project, environment and immutable revision independently.

A new host operation must include focused tests proving that arbitrary payload fields cannot change the executable or introduce shell evaluation.
