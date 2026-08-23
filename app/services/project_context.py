from __future__ import annotations

import hashlib
import json
import re
import tempfile
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mentor_models import ProjectSnapshot
from app.models import Project
from app.services.executor import ensure_repository, run

MAX_CONTEXT_FILES = 220
MAX_TARGET_CHARS = 12_000
MAX_SUMMARY_CHARS = 24_000

_TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".md",
    ".txt", ".ini", ".cfg", ".sh", ".sql", ".html", ".css", ".scss", ".go", ".rs",
    ".java", ".kt", ".php", ".rb", ".cs", ".xml",
}
_SENSITIVE_NAME = re.compile(
    r"(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx|crt)$|id_rsa|id_ed25519|credentials?\.json$|secrets?\.)",
    re.IGNORECASE,
)
_SECRET_LINE = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|passwd|authorization|private[_-]?key)\s*[:=]\s*([^\s#]+)"
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\"']+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)
_IMPORTANT_NAMES = {
    "README.md", "AGENTS.md", "pyproject.toml", "requirements.txt", "package.json",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Dockerfile", "docker-compose.yml",
    "compose.yaml", "render.yaml", "vercel.json", ".github/workflows/ci.yml",
}


def _safe_target(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Target path must stay inside the repository")
    return str(path)


def _redact_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}=[REDACTED]"

    # Redact structured bearer/token formats before the generic key=value rule.
    # Otherwise `Authorization: Bearer <opaque-token>` could become
    # `Authorization=[REDACTED] <opaque-token>` and leave the credential behind.
    redacted = _SECRET_VALUE_PATTERNS[0].sub(r"\1[REDACTED]", text)
    for pattern in _SECRET_VALUE_PATTERNS[1:]:
        redacted = pattern.sub("[REDACTED]", redacted)
    redacted = _SECRET_LINE.sub(replace, redacted)
    return redacted


def _git(repository: Path, args: list[str]) -> str:
    result = run(["git", *args], cwd=repository, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Unable to inspect repository")
    return result.stdout.strip()


def repository_commit(repository: Path, branch: str) -> str:
    for ref in (f"origin/{branch}", "HEAD"):
        result = run(["git", "rev-parse", ref], cwd=repository, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError("Unable to resolve repository commit")


@contextmanager
def readonly_worktree(project: Project) -> Iterator[tuple[Path, str]]:
    """Yield a disposable checkout pinned to the exact commit being inspected."""
    repository = ensure_repository(project)
    commit_sha = repository_commit(repository, project.default_branch)
    project_marker = str(getattr(project, "id", "project"))[:8]
    with tempfile.TemporaryDirectory(prefix=f"devpilot-context-{project_marker}-") as temp_dir:
        checkout = Path(temp_dir) / "repository"
        result = run(
            ["git", "worktree", "add", "--detach", str(checkout), commit_sha],
            cwd=repository,
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Unable to prepare read-only repository snapshot")
        try:
            yield checkout, commit_sha
        finally:
            cleanup = run(
                ["git", "worktree", "remove", "--force", str(checkout)],
                cwd=repository,
                timeout=60,
            )
            if cleanup.returncode:
                run(["git", "worktree", "prune"], cwd=repository, timeout=30)


def build_project_context(project: Project, target: str | None = None) -> dict:
    with readonly_worktree(project) as (repository, commit_sha):
        output = _git(repository, ["ls-files"])
        tracked = [line.strip() for line in output.splitlines() if line.strip()]
        safe_files = [path for path in tracked if not _SENSITIVE_NAME.search(path)]
        sampled = safe_files[:MAX_CONTEXT_FILES]

        suffixes = Counter((PurePosixPath(path).suffix.lower() or "[no-extension]") for path in safe_files)
        roots = Counter(PurePosixPath(path).parts[0] for path in safe_files if PurePosixPath(path).parts)
        important = [
            path
            for path in safe_files
            if path in _IMPORTANT_NAMES or PurePosixPath(path).name in _IMPORTANT_NAMES
        ]

        target_path = _safe_target(target)
        target_excerpt = ""
        if target_path:
            if target_path not in tracked:
                raise ValueError("Target file is not tracked by Git")
            if _SENSITIVE_NAME.search(target_path):
                raise ValueError("Sensitive files cannot be added to AI context")
            suffix = PurePosixPath(target_path).suffix.lower()
            if suffix not in _TEXT_SUFFIXES and PurePosixPath(target_path).name not in {"Dockerfile", "Makefile"}:
                raise ValueError("Target file is not an allowed text file")
            file_path = repository / target_path
            if not file_path.is_file():
                raise ValueError("Target file is unavailable in the repository snapshot")
            target_excerpt = _redact_text(
                file_path.read_text(encoding="utf-8", errors="replace")[:MAX_TARGET_CHARS]
            )

        summary = {
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "default_branch": project.default_branch,
            },
            "commit_sha": commit_sha,
            "tracked_file_count": len(tracked),
            "safe_file_count": len(safe_files),
            "sampled_files": sampled,
            "top_extensions": suffixes.most_common(16),
            "top_roots": roots.most_common(16),
            "important_files": important[:40],
            "target": target_path,
            "target_excerpt": target_excerpt,
            "context_limits": {
                "sampled_files": MAX_CONTEXT_FILES,
                "target_chars": MAX_TARGET_CHARS,
            },
        }
        encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        if len(encoded) > MAX_SUMMARY_CHARS:
            summary["sampled_files"] = sampled[:100]
            encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        summary["context_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return summary


def get_or_create_snapshot(
    db: Session,
    *,
    project: Project,
    target: str | None = None,
) -> tuple[ProjectSnapshot, dict]:
    summary = build_project_context(project, target=target)
    snapshot = db.scalar(
        select(ProjectSnapshot).where(
            ProjectSnapshot.project_id == project.id,
            ProjectSnapshot.commit_sha == summary["commit_sha"],
            ProjectSnapshot.context_hash == summary["context_hash"],
        )
    )
    if snapshot:
        # Reuse only the snapshot identity. Target excerpts are rebuilt in memory and
        # are never persisted, which avoids turning the database into a source-code cache.
        return snapshot, summary

    persisted_summary = dict(summary)
    persisted_summary["target_excerpt"] = ""
    snapshot = ProjectSnapshot(
        workspace_id=project.workspace_id,
        project_id=project.id,
        commit_sha=summary["commit_sha"],
        context_hash=summary["context_hash"],
        summary_json=json.dumps(persisted_summary, ensure_ascii=False),
    )
    db.add(snapshot)
    db.flush()
    return snapshot, summary
