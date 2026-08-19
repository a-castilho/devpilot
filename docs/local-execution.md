# Local task execution

DevPilot has two execution paths for repository tasks. The default routing mode is `auto`.

## Routing

- Explicit read-only tasks run through local Ollama.
- Repository-writing implementation tasks run through Codex CLI.
- `DEVPILOT_EXECUTION_ENABLED=false` keeps both paths in dry-run mode.

Read-only intent is recognized only when the task contains a strong non-mutation instruction such as
`somente leitura`, `não modifique`, `não altere`, `read-only`, or an equivalent marker. This is
intentionally conservative so an implementation task is not accidentally downgraded to analysis.

## True read-only behavior

The local read-only executor does not create a task branch and does not write configured project
instructions into `AGENTS.md`. Instead, it:

1. fetches the repository through the existing safe Git command path;
2. reads committed content directly from `origin/<default_branch>` using Git object commands;
3. excludes common secret-bearing files, generated directories, caches, archives/binaries and
   oversized blobs;
4. builds a bounded context suitable for the 4 GB profile;
5. sends that context plus the task and project policy to Ollama over HTTP;
6. verifies that the repository worktree status is exactly unchanged before and after analysis.

The default local budget is 40 files, 8,000 characters per file and 40,000 characters total.

## Project instructions

`Project.agents_md` is now injected into the execution prompt as authoritative project policy. DevPilot
never writes that value into the repository checkout. A tracked repository `AGENTS.md` remains part of
the repository itself and can be read as committed project context.

Older DevPilot versions may have left a generated, untracked `AGENTS.md` in a DevPilot-managed clone.
The new executor does not delete untracked user data automatically. Inspect it before removing it.

## Configuration

```text
DEVPILOT_TASK_EXECUTOR=auto
DEVPILOT_LOCAL_READONLY_ENABLED=true
DEVPILOT_LOCAL_READONLY_MAX_FILES=40
DEVPILOT_LOCAL_READONLY_MAX_FILE_CHARS=8000
DEVPILOT_LOCAL_READONLY_MAX_CONTEXT_CHARS=40000
DEVPILOT_OLLAMA_BASE_URL=http://127.0.0.1:11434
DEVPILOT_OLLAMA_CHAT_MODEL=gemma3:1b
```

Project `codex_config` may override `executor` with `auto`, `codex`, or `ollama`. The `ollama` task
executor is intentionally read-only; it refuses repository-writing tasks.

## One-command preflight

Run the local readiness check before starting real execution:

```bash
python -m app.preflight
```

It reports Python, Git, Codex, Ollama/model availability, repository-directory readiness and the
active task-execution configuration. Checks become required according to the configured execution
mode, so a missing local model is clearly distinguished from an optional capability.

## Ollama preflight

Before running local analysis, ensure Ollama is available and the configured model exists. A typical
host setup is:

```bash
ollama list
ollama pull gemma3:1b
```

If Ollama or the model is unavailable, the task fails closed with an actionable message instead of
falling back to a mutating executor.

## Results and failures

The worker prints only safe task metadata and a bounded summary to stdout. It does not print task
prompts or provider secrets.

The dashboard exposes a `Resultado` action for review, completed and failed tasks. The result dialog
shows the run summary, executor/provider/model metadata and the bounded execution output.

The API equivalent is:

```text
GET /api/tasks/{task_id}/runs
```

Codex JSONL errors are parsed into the run summary, so quota failures and provider diagnostics are
visible without querying SQLite manually.

## Safety invariants

- no shell strings;
- no automatic push, merge or deploy;
- no automatic deletion of dirty/untracked repository content;
- read-only analysis never checks out a task branch;
- local analysis reads only bounded committed text from the selected Git ref;
- `.env`, private-key formats and credential/secret-named files are excluded;
- write tasks remain on the existing controlled Codex branch path.
