from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from app.config import get_settings
from app.models import Project, Task
from app.services.results import extract_summary, extract_usage


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def run(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides or {})
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )


def ensure_repository(project: Project, github_token: str = "") -> Path:
    path = repository_path(project)
    git_env = {"GIT_TERMINAL_PROMPT": "0"}
    if github_token:
        git_env.update(
            GIT_ASKPASS="/usr/local/bin/devpilot-git-askpass",
            DEVPILOT_GITHUB_TOKEN=github_token,
        )
    if not path.exists():
        result = run(
            ["git", "clone", "--filter=blob:none", project.repository_url, str(path)],
            env_overrides=git_env,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Unable to clone repository")
    result = run(["git", "fetch", "--prune", "origin"], cwd=path, env_overrides=git_env)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to fetch repository")
    return path


def prepare_branch(path: Path, project: Project, branch: str) -> None:
    remote_ref = f"refs/remotes/origin/{project.default_branch}"
    exists = run(["git", "show-ref", "--verify", "--quiet", remote_ref], cwd=path)
    if exists.returncode == 0:
        checkout = run(["git", "switch", "-C", branch, remote_ref], cwd=path)
    else:
        checkout = run(["git", "switch", "--orphan", branch], cwd=path)
    if checkout.returncode:
        raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")


def execute_task(
    project: Project,
    task: Task,
    *,
    openai_api_key: str = "",
    github_token: str = "",
) -> dict:
    settings = get_settings()
    if not settings.execution_enabled:
        return {
            "mode": "dry-run",
            "summary": "Execution is disabled; task and audit trail were created successfully.",
            "planned_command": ["codex", "exec", "--json", "<task prompt>"],
        }
    if not openai_api_key:
        raise RuntimeError("Conecte uma credencial OpenAI antes de executar tarefas")
    path = ensure_repository(project, github_token)
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    prepare_branch(path, project, branch)
    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")
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
    result = run(
        command,
        cwd=path,
        timeout=int(config.get("timeout_seconds", 1800)),
        env_overrides={"OPENAI_API_KEY": openai_api_key},
    )
    response = {
        "mode": "execute",
        "exit_code": result.returncode,
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
        "summary": extract_summary(result.stdout),
        "usage": extract_usage(result.stdout),
    }
    agents_file = path / "AGENTS.md"
    if result.returncode == 0 and agents_file.is_file():
        response["generated_agents_md"] = agents_file.read_text(encoding="utf-8")[:100_000]
    return response
