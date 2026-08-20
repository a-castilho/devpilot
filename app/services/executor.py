from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Organization, Project, ProviderCredential, Task
from app.services.vault import Vault


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
READ_ONLY_MODE_MARKER = "[DEVPILOT_MODE=analysis-read-only]"
DEVELOPMENT_DUPLICATE_GUARD = (
    "MANDATORY FIRST PHASE — DUPLICATION PREFLIGHT. Before editing any file, inspect the repository "
    "for an existing implementation equivalent to the requested behavior. Check routes, screens, "
    "components, services, models, tests, configuration and documentation as relevant. Do not create "
    "a parallel or second implementation of behavior that already exists. If the feature already "
    "exists completely, make no implementation change merely to satisfy the task: validate it with "
    "the relevant checks and report the evidence. If it exists partially, reuse and extend the "
    "existing implementation and change only the verified gaps. Prefer adapting existing files and "
    "flows over adding duplicate endpoints, screens, components, services or models."
)


def repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def run(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if env_overrides:
        environment.update(env_overrides)
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=environment,
    )


def github_basic_authorization(access_token: str) -> str:
    encoded = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    return f"Authorization: Basic {encoded}"


def git_environment(project: Project) -> dict[str, str]:
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    if not project.organization_id:
        return environment

    with SessionLocal() as db:
        organization = db.scalar(
            select(Organization).where(Organization.id == project.organization_id)
        )
        if not organization or not organization.credential_id:
            return environment
        credential = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.id == organization.credential_id,
                ProviderCredential.provider == "github",
                ProviderCredential.enabled.is_(True),
            )
        )
        if not credential:
            return environment
        try:
            access_token = Vault().decrypt(credential.encrypted_secret)
        except ValueError as error:
            raise RuntimeError("GitHub organization credential cannot be decrypted") from error

    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": github_basic_authorization(access_token),
        }
    )
    return environment


def ensure_repository(project: Project) -> Path:
    path = repository_path(project)
    git_env = git_environment(project)
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


def is_read_only_task(task: Task) -> bool:
    prompt = str(task.prompt or "")
    normalized = prompt.casefold()
    return READ_ONLY_MODE_MARKER.casefold() in normalized or "não modifique arquivos" in normalized


def codex_command(project: Project, prompt: str) -> list[str]:
    config = json.loads(project.codex_config or "{}")
    command = ["codex", "exec", "--json"]
    if model := config.get("model"):
        command.extend(["--model", str(model)])
    command.append(prompt)
    return command


def task_timeout(project: Project) -> int:
    config = json.loads(project.codex_config or "{}")
    return int(config.get("timeout_seconds", 1800))


def development_prompt(task: Task) -> str:
    return (
        f"Task: {task.title}\n\n{task.prompt}\n\n"
        f"{DEVELOPMENT_DUPLICATE_GUARD}\n\n"
        "Only after completing that preflight, implement the smallest complete change that is still "
        "necessary, run relevant checks, and summarize the preflight evidence, changes and remaining "
        "risks. Do not push or merge."
    )


def execute_read_only_analysis(project: Project, task: Task, repository: Path) -> dict:
    """Run analysis in a disposable worktree so tracked project files are never persisted."""
    with tempfile.TemporaryDirectory(prefix=f"devpilot-analysis-{task.id[:8]}-") as temp_dir:
        analysis_path = Path(temp_dir) / "repository"
        worktree = run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(analysis_path),
                f"origin/{project.default_branch}",
            ],
            cwd=repository,
        )
        if worktree.returncode:
            raise RuntimeError(worktree.stderr.strip() or "Unable to prepare isolated analysis workspace")

        try:
            rules = (
                f"\n\nProject instructions (reference only):\n{project.agents_md}"
                if project.agents_md
                else ""
            )
            prompt = (
                f"Task: {task.title}\n\n{task.prompt}{rules}\n\n"
                "This is a READ-ONLY ANALYSIS. Inspect the repository and produce a technical report "
                "with concrete evidence, risks, impact, recommendations, and estimated effort. "
                "Do not implement, edit, create, delete, rename, commit, push, or merge project files. "
                "If a change would be useful, describe it instead of applying it."
            )
            result = run(
                codex_command(project, prompt),
                cwd=analysis_path,
                timeout=task_timeout(project),
            )
            status = run(["git", "status", "--porcelain"], cwd=analysis_path)
            attempted_changes = bool(status.stdout.strip()) if status.returncode == 0 else None
            return {
                "mode": "analysis-read-only",
                "exit_code": result.returncode,
                "summary": "Read-only analysis completed in an isolated disposable worktree.",
                "stdout": result.stdout[-100_000:],
                "stderr": result.stderr[-20_000:],
                "attempted_changes": attempted_changes,
                "persisted_changes": False,
                "branch": "",
            }
        finally:
            run(["git", "worktree", "remove", "--force", str(analysis_path)], cwd=repository)
            run(["git", "worktree", "prune"], cwd=repository)


def execute_task(project: Project, task: Task) -> dict:
    settings = get_settings()
    read_only = is_read_only_task(task)
    if not settings.execution_enabled:
        return {
            "mode": "analysis-read-only-dry-run" if read_only else "dry-run",
            "summary": "Execution is disabled; task and audit trail were created successfully.",
            "planned_command": ["codex", "exec", "--json", "<task prompt>"],
        }

    path = ensure_repository(project)
    if read_only:
        return execute_read_only_analysis(project, task, path)

    if project.agents_md:
        (path / "AGENTS.md").write_text(project.agents_md, encoding="utf-8")
    branch = task.branch_name or f"devpilot/{task.id[:8]}"
    checkout = run(["git", "switch", "-C", branch, f"origin/{project.default_branch}"], cwd=path)
    if checkout.returncode:
        raise RuntimeError(checkout.stderr.strip() or "Unable to create task branch")
    result = run(
        codex_command(project, development_prompt(task)),
        cwd=path,
        timeout=task_timeout(project),
    )
    return {
        "mode": "execute",
        "exit_code": result.returncode,
        "summary": "Execution completed on an isolated task branch after duplicate preflight.",
        "stdout": result.stdout[-100_000:],
        "stderr": result.stderr[-20_000:],
        "branch": branch,
    }
