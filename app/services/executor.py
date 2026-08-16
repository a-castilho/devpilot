from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from app.config import get_settings
from app.models import Project, Task


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


def execute_task(project: Project, task: Task) -> dict:
    settings = get_settings()
    if not settings.execution_enabled:
        return {
            "mode": "dry-run",
            "summary": "Execution is disabled; task and audit trail were created successfully.",
            "planned_command": ["codex", "exec", "--json", "<task prompt>"],
        }
    path = ensure_repository(project)
    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    checkout = run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=path)
    if checkout.returncode:
        raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")
    prompt = (
        f"Task: {task.title}\n\n{task.prompt}\n\n"
        "Inspect the repository, implement the smallest complete change, run relevant checks, "
        "and summarize changes and remaining risks. Do not push or merge."
    )
    config = json.loads(project.codex_config or "{}")
    command = ["codex", "exec", "--json"]
    if model := config.get("model"):
        command.extend(["--model", str(model)])
    command.append(prompt)
    result = run(command, cwd=path, timeout=int(config.get("timeout_seconds", 1800)))
    response = {
        "mode": "execute",
        "exit_code": result.returncode,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }
    agents_file = path / "AGENTS.md"
    if result.returncode == 0 and agents_file.is_file():
        response["generated_agents_md"] = agents_file.read_text(encoding="utf-8")[:100_000]
    return response
