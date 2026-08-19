from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from app.config import get_settings
from app.models import Project, Task
from app.services.local_executor import execute_read_only_agentos, execute_read_only_ollama, is_read_only_task


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def run(args: list[str], cwd: Path | None = None, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


def ensure_repository(project: Project) -> Path:
    path = repository_path(project)
    if not path.exists():
        result = run(["git", "clone", "--filter=blob:none", project.repository_url, str(path)])
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Unable to clone repository")
    result = run(["git", "fetch", "--prune", "origin"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to fetch repository")
    return path


def _project_instructions(project: Project) -> str:
    instructions = project.agents_md.strip()
    if not instructions:
        return ""
    return (
        "\n\nAdditional DevPilot project instructions (authoritative; do not write these into the repository):\n"
        f"{instructions[:100_000]}"
    )


def _extract_codex_message(stdout: str, stderr: str) -> str:
    """Extract the most useful user-facing message from Codex JSONL output."""

    for line in reversed(stdout.splitlines()):
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("type") == "error" and item.get("message"):
            return str(item["message"])[:4_000]
        error = item.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:4_000]
    if stderr.strip():
        return stderr.strip()[-4_000:]
    for line in reversed(stdout.splitlines()):
        if line.strip():
            return line.strip()[-4_000:]
    return "Codex execution failed without a diagnostic message"


def _execute_codex(project: Project, task: Task, *, path: Path, config: dict) -> dict:
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    checkout = run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=path)
    if checkout.returncode:
        raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")

    prompt = (
        f"Task: {task.title}\n\n{task.prompt}"
        f"{_project_instructions(project)}\n\n"
        "Inspect the repository, implement the smallest complete change, run relevant checks, "
        "and summarize changes and remaining risks. Do not push, merge, deploy, modify credentials, "
        "perform destructive migrations, or change production resources without explicit human approval."
    )
    command = ["codex", "exec", "--json"]
    if model := config.get("model"):
        command.extend(["--model", str(model)])
    command.append(prompt)
    result = run(command, cwd=path, timeout=int(config.get("timeout_seconds", 1800)))
    summary = (
        "Codex repository execution completed successfully."
        if result.returncode == 0
        else _extract_codex_message(result.stdout, result.stderr)
    )
    return {
        "mode": "execute",
        "executor": "codex",
        "exit_code": result.returncode,
        "summary": summary,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
        "read_only": False,
    }


def execute_task(project: Project, task: Task) -> dict:
    settings = get_settings()
    config = json.loads(project.codex_config or "{}")
    configured_executor = str(config.get("executor") or settings.task_executor).strip().lower()
    if configured_executor not in {"auto", "codex", "ollama"}:
        raise RuntimeError(f"Unsupported task executor: {configured_executor}")

    read_only = is_read_only_task(task)
    if not settings.execution_enabled:
        if read_only and configured_executor == "auto":
            planned = "agentos-read-only"
        elif read_only and configured_executor == "ollama":
            planned = "ollama-read-only"
        else:
            planned = "codex"
        return {
            "mode": "dry-run",
            "executor": planned,
            "summary": "Execution is disabled; task and audit trail were created successfully.",
            "planned_command": [planned, "<task prompt>"],
            "read_only": read_only,
        }

    path = ensure_repository(project)

    # True read-only work never checks out a task branch and never writes the configured AGENTS.md.
    # auto uses the configured AgentOS model gateway; explicit ollama preserves local-only behavior.
    if read_only and configured_executor in {"auto", "ollama"}:
        if not settings.local_readonly_enabled:
            raise RuntimeError("Local read-only execution is disabled")
        if configured_executor == "auto":
            return execute_read_only_agentos(project, task, path=path)
        return execute_read_only_ollama(project, task, path=path)

    if configured_executor == "ollama":
        raise RuntimeError(
            "The local Ollama task executor is read-only. Use executor=auto/codex for repository-writing tasks."
        )

    return _execute_codex(project, task, path=path, config=config)
