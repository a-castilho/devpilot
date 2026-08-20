from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import object_session

from app.config import get_settings
from app.models import Project, ProviderCredential, Task
from app.services.local_executor import execute_read_only_agentos, execute_read_only_ollama, is_read_only_task
from app.services.vault import Vault


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
USAGE_LIMIT_MARKERS = (
    "usage limit",
    "hit your usage limit",
    "purchase more credits",
    "buy more credits",
    "try again at",
)
RATE_LIMIT_MARKERS = (
    "rate limit",
    "too many requests",
    "http 429",
    "status 429",
)
AUTH_MARKERS = (
    "invalid api key",
    "incorrect api key",
    "unauthorized",
    "authentication failed",
    "status 401",
    "status 403",
)
TRANSIENT_MARKERS = (
    "temporarily unavailable",
    "connection reset",
    "connection refused",
    "timed out",
    "timeout",
    "status 502",
    "status 503",
    "status 504",
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


def _classify_codex_failure(stdout: str, stderr: str) -> dict[str, object]:
    message = _extract_codex_message(stdout, stderr)
    normalized = f"{message}\n{stdout[-8_000:]}\n{stderr[-4_000:]}".lower()
    if any(marker in normalized for marker in USAGE_LIMIT_MARKERS):
        return {
            "code": "usage_limit",
            "message": "Limite do Codex atingido. A tarefa foi preservada e pode ser reexecutada.",
            "retryable": True,
            "blocked": True,
        }
    if any(marker in normalized for marker in RATE_LIMIT_MARKERS):
        return {
            "code": "rate_limit",
            "message": "O Codex limitou temporariamente a execução. A tarefa pode ser reexecutada.",
            "retryable": True,
            "blocked": True,
        }
    if any(marker in normalized for marker in AUTH_MARKERS):
        return {
            "code": "auth",
            "message": "A autenticação do executor foi rejeitada. Revise a conexão antes de reexecutar.",
            "retryable": False,
            "blocked": True,
        }
    if any(marker in normalized for marker in TRANSIENT_MARKERS):
        return {
            "code": "transient",
            "message": "O executor ficou temporariamente indisponível. A tarefa pode ser reexecutada.",
            "retryable": True,
            "blocked": True,
        }
    return {
        "code": "execution",
        "message": message,
        "retryable": False,
        "blocked": False,
    }


def _repository_status(path: Path) -> str:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=path)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to inspect repository status")
    return result.stdout


def _saved_openai_api_key(task: Task, *, connection_label: str = "") -> str:
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
    item = db.scalar(query.order_by(ProviderCredential.created_at.desc()).limit(1))
    if not item:
        return ""
    try:
        return Vault().decrypt(item.encrypted_secret).strip()
    except (RuntimeError, ValueError):
        return ""


def _codex_command(config: dict, prompt: str) -> list[str]:
    command = ["codex", "exec", "--json"]
    if model := config.get("model"):
        command.extend(["--model", str(model)])
    command.append(prompt)
    return command


def _codex_attempt(
    *,
    command: list[str],
    path: Path,
    timeout: int,
    provider: str,
    auth_mode: str,
    env_overrides: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    result = run(command, cwd=path, timeout=timeout, env_overrides=env_overrides)
    attempt: dict[str, object] = {
        "provider": provider,
        "auth_mode": auth_mode,
        "exit_code": result.returncode,
    }
    if result.returncode:
        failure = _classify_codex_failure(result.stdout, result.stderr)
        attempt.update(
            failure_code=failure["code"],
            retryable=failure["retryable"],
            summary=failure["message"],
        )
    else:
        attempt.update(summary="Execução concluída.", retryable=False)
    return result, attempt


def _api_key_codex_attempt(
    *,
    command: list[str],
    path: Path,
    timeout: int,
    api_key: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    """Run Codex with API-key auth isolated from the user's ~/.codex ChatGPT session."""

    with tempfile.TemporaryDirectory(prefix="devpilot-codex-api-") as directory:
        codex_home = Path(directory)
        auth_file = codex_home / "auth.json"
        auth_file.write_text(
            json.dumps({"auth_mode": "api_key", "OPENAI_API_KEY": api_key}),
            encoding="utf-8",
        )
        auth_file.chmod(0o600)
        return _codex_attempt(
            command=command,
            path=path,
            timeout=timeout,
            provider="openai-api",
            auth_mode="api_key",
            env_overrides={
                "CODEX_HOME": str(codex_home),
                "OPENAI_API_KEY": api_key,
            },
        )


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
    command = _codex_command(config, prompt)
    timeout = int(config.get("timeout_seconds", 1800))
    before = _repository_status(path)
    primary, primary_attempt = _codex_attempt(
        command=command,
        path=path,
        timeout=timeout,
        provider="chatgpt-codex",
        auth_mode="chatgpt_session",
    )
    attempts = [primary_attempt]

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
            "read_only": False,
            "attempts": attempts,
            "fallback_used": False,
        }

    primary_failure = _classify_codex_failure(primary.stdout, primary.stderr)
    after_primary = _repository_status(path)
    fallback_candidate = primary_failure["code"] in {"usage_limit", "rate_limit"}
    settings = get_settings()
    fallback_enabled = bool(config.get("api_fallback", settings.codex_api_fallback_enabled))
    fallback_label = str(
        config.get("api_fallback_connection_label")
        or settings.codex_api_fallback_connection_label
        or ""
    )
    api_key = _saved_openai_api_key(task, connection_label=fallback_label) if fallback_enabled else ""

    if fallback_candidate and after_primary != before:
        return {
            "mode": "execute",
            "executor": "codex",
            "provider": "chatgpt-codex",
            "auth_mode": "chatgpt_session",
            "exit_code": primary.returncode,
            "summary": (
                "O Codex atingiu um limite depois de alterar a worktree. O DevPilot não fará fallback "
                "automático sobre um estado parcial; revise a branch antes de reexecutar."
            ),
            "stdout": primary.stdout[-100_000:],
            "stderr": primary.stderr[-20_000:],
            "branch": branch,
            "read_only": False,
            "failure_code": "partial_changes_detected",
            "retryable": False,
            "blocked": True,
            "attempts": attempts,
            "fallback_used": False,
            "suggested_action": "Revise a branch da tarefa e reexecute somente após confirmar o estado.",
        }

    if fallback_candidate and fallback_enabled and api_key:
        fallback, fallback_attempt = _api_key_codex_attempt(
            command=command,
            path=path,
            timeout=timeout,
            api_key=api_key,
        )
        attempts.append(fallback_attempt)
        if fallback.returncode == 0:
            return {
                "mode": "execute",
                "executor": "codex",
                "provider": "openai-api",
                "auth_mode": "api_key",
                "exit_code": 0,
                "summary": "Codex concluiu a tarefa usando o fallback OpenAI API após o limite da sessão ChatGPT.",
                "stdout": fallback.stdout[-100_000:],
                "stderr": fallback.stderr[-20_000:],
                "branch": branch,
                "read_only": False,
                "attempts": attempts,
                "fallback_used": True,
                "fallback_reason": primary_failure["code"],
                "paid_api_fallback": True,
            }
        fallback_failure = _classify_codex_failure(fallback.stdout, fallback.stderr)
        return {
            "mode": "execute",
            "executor": "codex",
            "provider": "openai-api",
            "auth_mode": "api_key",
            "exit_code": fallback.returncode,
            "summary": fallback_failure["message"],
            "stdout": fallback.stdout[-100_000:],
            "stderr": fallback.stderr[-20_000:],
            "branch": branch,
            "read_only": False,
            "failure_code": fallback_failure["code"],
            "retryable": fallback_failure["retryable"],
            "blocked": fallback_failure["blocked"],
            "attempts": attempts,
            "fallback_used": True,
            "fallback_reason": primary_failure["code"],
            "paid_api_fallback": True,
            "suggested_action": "Revise a conexão OpenAI/API e use Reexecutar quando houver capacidade disponível.",
        }

    suggested_action = (
        "Cadastre uma conexão OpenAI em Modelos de IA para habilitar o fallback por API, "
        "adicione créditos/aguarde a renovação do Codex e depois use Reexecutar."
        if fallback_candidate and not api_key
        else "Use Reexecutar quando o executor estiver disponível."
    )
    return {
        "mode": "execute",
        "executor": "codex",
        "provider": "chatgpt-codex",
        "auth_mode": "chatgpt_session",
        "exit_code": primary.returncode,
        "summary": primary_failure["message"],
        "stdout": primary.stdout[-100_000:],
        "stderr": primary.stderr[-20_000:],
        "branch": branch,
        "read_only": False,
        "failure_code": primary_failure["code"],
        "retryable": primary_failure["retryable"],
        "blocked": primary_failure["blocked"],
        "attempts": attempts,
        "fallback_used": False,
        "fallback_available": bool(api_key),
        "suggested_action": suggested_action,
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
