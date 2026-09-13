from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Callable

from app.config import get_settings
from app.models import Project


SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")
RunCommand = Callable[..., object]


class GitHubRepositoryAccessError(RuntimeError):
    """Raised when DevPilot cannot prove access to a GitHub repository before checkout."""


def _repository_path(project: Project) -> Path:
    return get_settings().repositories_dir / SAFE_NAME.sub("-", project.slug)


def _git_environment(access_token: str | None = None) -> dict[str, str]:
    environment = {"GIT_TERMINAL_PROMPT": "0"}
    if not access_token:
        return environment
    encoded = base64.b64encode(f"x-access-token:{access_token}".encode()).decode()
    environment.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
        }
    )
    return environment


def _public_repository_access(project: Project, run_command: RunCommand) -> bool:
    """Return True when the exact repository can be read without credentials."""
    result = run_command(
        ["git", "ls-remote", project.repository_url, "HEAD"],
        timeout=45,
        env_overrides={"GIT_TERMINAL_PROMPT": "0"},
    )
    return getattr(result, "returncode", 1) == 0


def _resolved_git_environment(project: Project, run_command: RunCommand) -> dict[str, str]:
    """Resolve repository access before clone/fetch.

    Public repositories are accepted without credentials. Otherwise the canonical
    GitHub access resolver validates every enabled GitHub credential in the workspace,
    repairs stale project/organization bindings when possible and returns the proven
    authentication environment. No clone/fetch is attempted until access is proven.
    """
    if _public_repository_access(project, run_command):
        return {"GIT_TERMINAL_PROMPT": "0"}

    from app.services.github_access_bridge import resolve_github_access

    resolution = resolve_github_access(project)
    if resolution.ok:
        return resolution.environment

    message = str(resolution.message or "Nenhuma credencial GitHub válida foi encontrada.").strip()
    raise GitHubRepositoryAccessError(f"repository access denied: {message}")


def _prepare_blueprint(project: Project, path: Path) -> None:
    """Best-effort blueprint seeding; generation remains usable if the optional layer is absent."""
    try:
        from app.blueprint_execution import prepare_blueprint_workspace

        prepare_blueprint_workspace(project, path)
    except (ImportError, KeyError, ValueError, OSError) as error:
        raise RuntimeError(f"Blueprint workspace preparation failed: {error}") from error


def ensure_repository(project: Project, run_command: RunCommand) -> Path:
    """Prepare checkout only after DevPilot has proven repository access.

    This is a preflight gate: a private/inaccessible repository never reaches an
    unauthenticated ``git clone`` or ``git fetch``. After checkout, a selected blueprint
    is materialized by creating only files that do not already exist, so existing code
    is never overwritten and the AI generates only the remaining delta.
    """
    path = _repository_path(project)
    git_env = _resolved_git_environment(project, run_command)

    if not path.exists():
        result = run_command(
            ["git", "clone", "--filter=blob:none", project.repository_url, str(path)],
            env_overrides=git_env,
        )
        if getattr(result, "returncode", 1):
            raise RuntimeError(getattr(result, "stderr", "").strip() or "Unable to clone repository")

    result = run_command(
        ["git", "fetch", "--prune", "origin"],
        cwd=path,
        env_overrides=git_env,
    )
    if getattr(result, "returncode", 1):
        raise RuntimeError(getattr(result, "stderr", "").strip() or "Unable to fetch repository")

    _prepare_blueprint(project, path)
    return path
