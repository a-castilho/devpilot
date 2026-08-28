from __future__ import annotations

from pathlib import PurePosixPath

from app.models import Project
from app.services.executor import ensure_repository, run
from .sanitizer import RagSanitizer

TEXT_EXTENSIONS = {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yml", ".yaml", ".toml", ".sql", ".sh", ".css", ".html"}


class GitRagSource:
    def list_files(self, project: Project) -> list[str]:
        repository = ensure_repository(project)
        ref = f"origin/{project.default_branch}"
        result = run(["git", "ls-tree", "-r", "--name-only", ref], cwd=repository, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stderr.strip() or "Git file listing failed")[-4000:])
        files = []
        for raw in result.stdout.splitlines():
            path = raw.strip().replace("\\", "/")
            if not path or RagSanitizer.should_exclude_path(path):
                continue
            name = PurePosixPath(path).name
            if PurePosixPath(path).suffix.lower() in TEXT_EXTENSIONS or name in {"README", "Dockerfile", "Makefile"}:
                files.append(path)
        return files

    def read(self, project: Project, path: str) -> str:
        repository = ensure_repository(project)
        result = run(["git", "show", f"origin/{project.default_branch}:{path}"], cwd=repository, timeout=60)
        if result.returncode:
            raise RuntimeError((result.stderr.strip() or "Git file read failed")[-4000:])
        return result.stdout[:500000]
