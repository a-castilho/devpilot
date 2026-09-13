from __future__ import annotations

from pathlib import Path

from app.models import Project


_LOCAL_MARKER = ".devpilot-managed-local"


def ensure_managed_local_repository(project: Project) -> Path | None:
    """Prepare a Git-compatible local workspace for a DevPilot-managed project.

    Remote GitHub is a delivery dependency, not a prerequisite for planning/coding.
    This fallback is deliberately restricted to DevPilot-managed repositories. It
    preserves any existing files, creates an initial local commit when necessary and
    exposes a synthetic ``origin/<default_branch>`` ref so the existing executor and
    read-only worktree flows keep working unchanged.
    """
    from app.services import executor
    from app.services import github_access_bridge as bridge

    if not bridge._managed_repository(project):
        return None

    path = executor.repository_path(project)
    path.mkdir(parents=True, exist_ok=True)

    git_dir = path / ".git"
    if not git_dir.exists():
        initialized = executor.run(
            ["git", "init", "-b", str(project.default_branch or "main")],
            cwd=path,
            timeout=60,
        )
        if initialized.returncode:
            # Older Git versions may not support `init -b`.
            initialized = executor.run(["git", "init"], cwd=path, timeout=60)
            if initialized.returncode:
                raise RuntimeError(initialized.stderr.strip() or "Unable to initialize managed local repository")
            switched = executor.run(
                ["git", "checkout", "-B", str(project.default_branch or "main")],
                cwd=path,
                timeout=60,
            )
            if switched.returncode:
                raise RuntimeError(switched.stderr.strip() or "Unable to initialize managed local branch")

    executor.run(["git", "config", "user.name", "DevPilot"], cwd=path, timeout=30)
    executor.run(["git", "config", "user.email", "devpilot@local.invalid"], cwd=path, timeout=30)

    head = executor.run(["git", "rev-parse", "--verify", "HEAD"], cwd=path, timeout=30)
    if head.returncode:
        committed = executor.run(
            ["git", "commit", "--allow-empty", "-m", "chore: initialize DevPilot managed workspace"],
            cwd=path,
            timeout=60,
        )
        if committed.returncode:
            raise RuntimeError(committed.stderr.strip() or "Unable to create initial managed workspace commit")

    default_branch = str(project.default_branch or "main")
    # Existing execution code branches/worktrees from origin/<default>. A local
    # tracking ref gives it an immutable baseline without pretending a remote exists.
    ref = executor.run(
        ["git", "update-ref", f"refs/remotes/origin/{default_branch}", "HEAD"],
        cwd=path,
        timeout=30,
    )
    if ref.returncode:
        raise RuntimeError(ref.stderr.strip() or "Unable to prepare managed local baseline")

    marker = path / _LOCAL_MARKER
    if not marker.exists():
        marker.write_text(
            "GitHub remoto pendente; desenvolvimento local gerenciado pelo DevPilot.\n",
            encoding="utf-8",
        )

    return path


def install_managed_local_repository_fallback() -> None:
    """Make remote GitHub failure non-terminal for DevPilot-managed projects."""
    from app.services import executor

    current = executor.ensure_repository
    if getattr(current, "_devpilot_managed_local_fallback", False):
        return

    def ensure_repository(project: Project):
        try:
            return current(project)
        except Exception:
            local = ensure_managed_local_repository(project)
            if local is None:
                raise
            print(
                f"[managed-local] continuing project={project.id} without GitHub remote "
                f"repo={project.repository_url}",
                flush=True,
            )
            return local

    setattr(ensure_repository, "_devpilot_managed_local_fallback", True)
    executor.ensure_repository = ensure_repository
