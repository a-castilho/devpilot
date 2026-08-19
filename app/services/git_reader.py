from __future__ import annotations

import re
from pathlib import PurePosixPath

from app.models import Project
from app.services.executor import ensure_repository, run


SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,179}$")
MAX_GREP_LINE = 4_000


def repository_ref(project: Project, ref: str | None = None) -> str:
    value = (ref or f"origin/{project.default_branch}").strip()
    if (
        not SAFE_REF.fullmatch(value)
        or ".." in value
        or "@{" in value
        or "//" in value
    ):
        raise ValueError("Invalid Git ref")
    return value


def repository_file_path(path: str) -> str:
    value = path.strip().replace("\\", "/")
    parsed = PurePosixPath(value)
    if not value or parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError("Invalid repository file path")
    return parsed.as_posix()


def _git(project: Project, args: list[str], timeout: int = 60) -> str:
    path = ensure_repository(project)
    result = run(["git", *args], cwd=path, timeout=timeout)
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise RuntimeError(message[-4_000:])
    return result.stdout


def status(project: Project) -> dict:
    output = _git(project, ["status", "--short", "--branch"], timeout=30)
    return {"repository": project.repository_url, "status": output.rstrip()}


def log(project: Project, limit: int = 20, ref: str | None = None) -> list[dict]:
    selected_ref = repository_ref(project, ref)
    output = _git(
        project,
        [
            "log",
            "-n",
            str(limit),
            "--date=iso-strict",
            "--pretty=format:%H%x1f%h%x1f%an%x1f%aI%x1f%s",
            selected_ref,
            "--",
        ],
        timeout=60,
    )
    commits: list[dict] = []
    for line in output.splitlines():
        parts = line.split("\x1f", 4)
        if len(parts) != 5:
            continue
        sha, short_sha, author, authored_at, subject = parts
        commits.append(
            {
                "sha": sha,
                "short_sha": short_sha,
                "author": author,
                "authored_at": authored_at,
                "subject": subject,
            }
        )
    return commits


def grep(
    project: Project,
    query: str,
    limit: int = 100,
    ref: str | None = None,
) -> list[dict]:
    selected_ref = repository_ref(project, ref)
    needle = query.strip()
    if not needle:
        raise ValueError("Search query is required")

    path = ensure_repository(project)
    result = run(
        ["git", "grep", "-n", "-I", "-F", "-e", needle, selected_ref, "--"],
        cwd=path,
        timeout=60,
    )
    if result.returncode not in {0, 1}:
        message = result.stderr.strip() or "Git grep failed"
        raise RuntimeError(message[-4_000:])

    matches: list[dict] = []
    for line in result.stdout.splitlines():
        if len(matches) >= limit:
            break
        prefix, separator, text = line.partition(":")
        if not separator:
            continue
        file_path, separator, line_number = prefix.rpartition(":")
        if not separator:
            continue
        try:
            number = int(line_number)
        except ValueError:
            continue
        matches.append(
            {
                "path": file_path.removeprefix(f"{selected_ref}:"),
                "line": number,
                "text": text[:MAX_GREP_LINE],
            }
        )
    return matches


def read_file(project: Project, path: str, ref: str | None = None) -> dict:
    selected_ref = repository_ref(project, ref)
    selected_path = repository_file_path(path)
    output = _git(project, ["show", f"{selected_ref}:{selected_path}"], timeout=60)
    return {
        "path": selected_path,
        "ref": selected_ref,
        "content": output[:200_000],
        "truncated": len(output) > 200_000,
    }
