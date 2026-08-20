from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import object_session

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


CODEX_AUTH_FAILURE_MARKERS = (
    "unauthorized",
    "authentication failed",
    "invalid api key",
    "incorrect api key",
    "http 401",
    "status 401",
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



def codex_authentication_rejected(stdout: str, stderr: str) -> bool:
    diagnostic = f"{stdout[-8_000:]}\n{stderr[-4_000:]}".lower()
    return any(marker in diagnostic for marker in CODEX_AUTH_FAILURE_MARKERS)


def _saved_openai_api_key(task: Task, connection_label: str = "") -> str:
    db = object_session(task)
    if db is None:
        return ""
    query = select(ProviderCredential).where(
        ProviderCredential.workspace_id == task.workspace_id,
        ProviderCredential.provider == "openai",
        ProviderCredential.enabled.is_(True),
    )
    if connection_label.strip():
        query = query.where(ProviderCredential.label == connection_label.strip())
    credential = db.scalar(query.order_by(ProviderCredential.created_at.desc()).limit(1))
    if not credential:
        return ""
    try:
        return Vault().decrypt(credential.encrypted_secret).strip()
    except (RuntimeError, ValueError):
        return ""


def _repository_status(path: Path) -> str:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to inspect repository status")
    return result.stdout


def _run_codex_with_openai_api_key(project: Project, prompt: str, api_key: str):
    """Run the fallback in an isolated Codex home; credentials never touch logs or Git."""
    with tempfile.TemporaryDirectory(prefix="devpilot-codex-api-") as temporary_directory:
        codex_home = Path(temporary_directory)
        auth_file = codex_home / "auth.json"
        auth_file.write_text(
            json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": api_key}),
            encoding="utf-8",
        )
        auth_file.chmod(0o600)
        return run(
            codex_command(project, prompt),
            cwd=repository_path(project),
            timeout=task_timeout(project),
            env_overrides={
                "CODEX_HOME": str(codex_home),
                "OPENAI_API_KEY": api_key,
            },
        )

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

    prompt = development_prompt(task)
    primary = run(
        codex_command(project, prompt),
        cwd=path,
        timeout=task_timeout(project),
    )
    if primary.returncode == 0:
        return {
            "mode": "execute",
            "executor": "codex",
            "provider": "chatgpt-codex",
            "auth_mode": "chatgpt_session",
            "exit_code": 0,
            "summary": "Codex repository execution completed successfully.",
            "stdout": primary.stdout[-100_000:],
            "stderr": primary.stderr[-20_000:],
            "branch": branch,
            "fallback_used": False,
        }

    if codex_authentication_rejected(primary.stdout, primary.stderr):
        config = json.loads(project.codex_config or "{}")
        fallback_enabled = bool(
            config.get("api_fallback", settings.codex_api_fallback_enabled)
        )
        connection_label = str(
            config.get("api_fallback_connection_label")
            or settings.codex_api_fallback_connection_label
            or ""
        )
        api_key = (
            _saved_openai_api_key(task, connection_label)
            if fallback_enabled
            else ""
        )
        if api_key:
            before_fallback = _repository_status(path)
            fallback = _run_codex_with_openai_api_key(project, prompt, api_key)
            after_fallback = _repository_status(path)
            if fallback.returncode == 0:
                return {
                    "mode": "execute",
                    "executor": "codex",
                    "provider": "openai-api",
                    "auth_mode": "api_key",
                    "exit_code": 0,
                    "summary": "Codex concluiu a tarefa com a conexão OpenAI segura após a sessão local ser rejeitada.",
                    "stdout": fallback.stdout[-100_000:],
                    "stderr": fallback.stderr[-20_000:],
                    "branch": branch,
                    "fallback_used": True,
                    "paid_api_fallback": True,
                    "failure_code": "auth",
                }
            if after_fallback != before_fallback:
                return {
                    "mode": "execute",
                    "executor": "codex",
                    "provider": "openai-api",
                    "auth_mode": "api_key",
                    "exit_code": fallback.returncode,
                    "summary": "A conexão OpenAI falhou após iniciar alterações. A branch foi preservada para revisão.",
                    "stdout": fallback.stdout[-100_000:],
                    "stderr": fallback.stderr[-20_000:],
                    "branch": branch,
                    "failure_code": "partial_changes_detected",
                    "blocked": True,
                    "fallback_used": True,
                    "paid_api_fallback": True,
                }
            return {
                "mode": "execute",
                "executor": "codex",
                "provider": "openai-api",
                "auth_mode": "api_key",
                "exit_code": fallback.returncode,
                "summary": "A conexão OpenAI cadastrada foi rejeitada. Atualize-a em Modelos de IA antes de reexecutar.",
                "stdout": fallback.stdout[-100_000:],
                "stderr": fallback.stderr[-20_000:],
                "branch": branch,
                "failure_code": "auth",
                "blocked": True,
                "fallback_used": True,
                "paid_api_fallback": True,
            }
        return {
            "mode": "execute",
            "executor": "codex",
            "provider": "chatgpt-codex",
            "auth_mode": "chatgpt_session",
            "exit_code": primary.returncode,
            "summary": "A sessão do Codex foi rejeitada. Cadastre ou atualize uma conexão OpenAI em Modelos de IA e use Reexecutar.",
            "stdout": primary.stdout[-100_000:],
            "stderr": primary.stderr[-20_000:],
            "branch": branch,
            "failure_code": "auth",
            "blocked": True,
            "fallback_used": False,
        }

    return {
        "mode": "execute",
        "executor": "codex",
        "provider": "chatgpt-codex",
        "auth_mode": "chatgpt_session",
        "exit_code": primary.returncode,
        "summary": primary.stderr.strip() or "Codex execution failed.",
        "stdout": primary.stdout[-100_000:],
        "stderr": primary.stderr[-20_000:],
        "branch": branch,
        "fallback_used": False,
    }
