from __future__ import annotations

from urllib.parse import urlparse

from app.services import executor

_INSTALLED = False
_ORIGINAL_GIT_ENVIRONMENT = executor.git_environment


def _anonymous_environment() -> dict[str, str]:
    return {"GIT_TERMINAL_PROMPT": "0"}


def _git_environment_with_public_fallback(project, repository_url: str | None = None) -> dict[str, str]:
    """Use anonymous Git for public GitHub repositories before attaching a PAT.

    A stale/underscoped organization token must not make a public repository
    inaccessible. Private repositories keep the existing credential path and
    security boundary unchanged.
    """
    environment = _ORIGINAL_GIT_ENVIRONMENT(project, repository_url)
    if "GIT_CONFIG_COUNT" not in environment:
        return environment

    safe_repository_url = repository_url or executor.validated_repository_url(project)
    if str(urlparse(safe_repository_url).hostname or "").lower() != executor.GITHUB_HOST:
        return environment

    try:
        probe = executor.run(
            ["git", "ls-remote", safe_repository_url, "HEAD"],
            timeout=30,
            env_overrides=_anonymous_environment(),
        )
    except (OSError, TimeoutError):
        return environment

    if probe.returncode == 0:
        return _anonymous_environment()
    return environment


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    executor.git_environment = _git_environment_with_public_fallback
    _INSTALLED = True


install()
