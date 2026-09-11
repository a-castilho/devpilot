from __future__ import annotations

from urllib.parse import urlparse

from app.github_repository_selfheal import repair_github_project
from app.services import executor

_ORIGINAL_ENSURE_REPOSITORY = executor.ensure_repository


def ensure_repository_with_preflight(project):
    """Anticipate GitHub failures before the worker reaches `git clone`.

    For GitHub projects DevPilot first validates/provisions the repository with the
    saved credential. This turns repository creation/access into a precondition of
    execution instead of discovering it after Codex has already started the task.
    Public repositories are still allowed to fall through to the normal checkout.
    """
    try:
        repository_url = executor.validated_repository_url(project)
    except Exception:
        return _ORIGINAL_ENSURE_REPOSITORY(project)

    if str(urlparse(repository_url).hostname or "").lower() == "github.com":
        try:
            repair_github_project(project)
        except Exception as error:
            # Preflight is self-healing best-effort. The normal checkout/recovery
            # path remains authoritative and will preserve a precise failure.
            print(f"[execution-preflight] {project.slug}: {type(error).__name__}: {error}", flush=True)

    return _ORIGINAL_ENSURE_REPOSITORY(project)


def install() -> None:
    if getattr(executor.ensure_repository, "_devpilot_preflight", False):
        return
    ensure_repository_with_preflight._devpilot_preflight = True
    executor.ensure_repository = ensure_repository_with_preflight


install()
