from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.application.intelligence import RepositoryIndexPort, RepositorySnapshotPort
from app.agentos.domain.intelligence import (
    DependencyEdge,
    DependencyGraph,
    RepositoryDocument,
    RepositoryIndexRecord,
    RepositorySnapshot,
)
from app.agentos.models import AgentRepositoryIndex
from app.models import Project
from app.services.executor import ensure_repository, repository_path


IGNORED_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build", ".next", ".cache",
    "coverage", "htmlcov", "logs", "data", "tmp", "temp", "__pycache__",
}
IGNORED_FILES = {".env", ".env.local", ".env.production", ".env.development"}
TEXT_EXTENSIONS = {
    ".py": ("python", "code"),
    ".js": ("javascript", "code"),
    ".jsx": ("javascript", "code"),
    ".ts": ("typescript", "code"),
    ".tsx": ("typescript", "code"),
    ".md": ("markdown", "docs"),
    ".rst": ("rst", "docs"),
    ".txt": ("text", "docs"),
    ".toml": ("toml", "config"),
    ".yaml": ("yaml", "config"),
    ".yml": ("yaml", "config"),
    ".json": ("json", "config"),
    ".sql": ("sql", "code"),
    ".html": ("html", "code"),
    ".css": ("css", "code"),
    ".scss": ("scss", "code"),
    ".sh": ("shell", "code"),
}
JS_IMPORT_RE = re.compile(
    r"(?:from\s+['\"]([^'\"]+)['\"]|import\s*(?:\([^)]*?\)\s*)?['\"]([^'\"]+)['\"]|require\(\s*['\"]([^'\"]+)['\"]\s*\))"
)


def _safe_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _classify(path: Path) -> tuple[str, str] | None:
    if path.name in IGNORED_FILES:
        return None
    if path.name.startswith(".env") and path.name != ".env.example":
        return None
    return TEXT_EXTENSIONS.get(path.suffix.lower())


def _python_modules(paths: set[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in paths:
        if not path.endswith(".py"):
            continue
        parts = list(PurePosixPath(path).with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            result[".".join(parts)] = path
    return result


def _resolve_python_import(module: str, modules: dict[str, str]) -> str | None:
    if module in modules:
        return modules[module]
    parts = module.split(".")
    while len(parts) > 1:
        parts.pop()
        candidate = ".".join(parts)
        if candidate in modules:
            return modules[candidate]
    return None


def _resolve_js_import(source: str, specifier: str, paths: set[str]) -> str | None:
    if not specifier.startswith("."):
        return None
    base = PurePosixPath(source).parent
    raw = str((base / specifier).as_posix())
    while raw.startswith("./"):
        raw = raw[2:]
    candidates = [raw]
    for ext in (".ts", ".tsx", ".js", ".jsx", ".json"):
        candidates.append(raw + ext)
        candidates.append(str(PurePosixPath(raw) / f"index{ext}"))
    return next((candidate for candidate in candidates if candidate in paths), None)


class LocalRepositorySnapshotAdapter(RepositorySnapshotPort):
    def __init__(
        self,
        db: Session,
        *,
        max_files: int = 400,
        max_file_chars: int = 100_000,
        max_total_chars: int = 2_000_000,
    ) -> None:
        self.db = db
        self.max_files = max_files
        self.max_file_chars = max_file_chars
        self.max_total_chars = max_total_chars

    def snapshot(self, *, project_id: str, refresh: bool = False) -> RepositorySnapshot:
        project = self.db.get(Project, project_id)
        if project is None:
            raise LookupError("Project not found")
        root = repository_path(project)
        if not root.exists() or refresh:
            root = ensure_repository(project)

        documents: list[RepositoryDocument] = []
        skipped = 0
        total_chars = 0
        truncated = False
        candidates = sorted(
            path for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(part in IGNORED_DIRS for part in path.relative_to(root).parts)
        )
        for path in candidates:
            classified = _classify(path)
            if classified is None:
                continue
            if len(documents) >= self.max_files or total_chars >= self.max_total_chars:
                truncated = True
                skipped += 1
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                skipped += 1
                continue
            if len(raw) > self.max_file_chars:
                raw = raw[: self.max_file_chars]
                truncated = True
            if total_chars + len(raw) > self.max_total_chars:
                allowed = self.max_total_chars - total_chars
                if allowed <= 0:
                    truncated = True
                    skipped += 1
                    continue
                raw = raw[:allowed]
                truncated = True
            total_chars += len(raw)
            language, kind = classified
            relative = _safe_relative(path, root)
            documents.append(
                RepositoryDocument(
                    path=relative,
                    language=language,
                    kind=kind,  # type: ignore[arg-type]
                    content=raw,
                    content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                )
            )

        digest = hashlib.sha256()
        for document in documents:
            digest.update(document.path.encode("utf-8"))
            digest.update(document.content_hash.encode("ascii"))
        return RepositorySnapshot(
            project_id=project_id,
            documents=tuple(documents),
            snapshot_hash=digest.hexdigest(),
            truncated=truncated,
            skipped_files=skipped,
        )

    def graph(self, snapshot: RepositorySnapshot) -> DependencyGraph:
        paths = {document.path for document in snapshot.documents}
        modules = _python_modules(paths)
        edges: set[tuple[str, str, str]] = set()

        for document in snapshot.documents:
            if document.language == "python":
                try:
                    tree = ast.parse(document.content, filename=document.path)
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    names: list[str] = []
                    if isinstance(node, ast.Import):
                        names.extend(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        names.append(node.module)
                    for name in names:
                        target = _resolve_python_import(name, modules)
                        if target and target != document.path:
                            edges.add((document.path, target, "imports"))
            elif document.language in {"javascript", "typescript"}:
                for match in JS_IMPORT_RE.finditer(document.content):
                    specifier = next((item for item in match.groups() if item), "")
                    target = _resolve_js_import(document.path, specifier, paths)
                    if target and target != document.path:
                        edges.add((document.path, target, "imports"))

        return DependencyGraph(
            nodes=tuple(sorted(paths)),
            edges=tuple(
                DependencyEdge(source=source, target=target, relation=relation)
                for source, target, relation in sorted(edges)
            ),
        )


class SQLAlchemyRepositoryIndex(RepositoryIndexPort):
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _record(item: AgentRepositoryIndex) -> RepositoryIndexRecord:
        return RepositoryIndexRecord(
            project_id=item.project_id,
            workspace_id=item.workspace_id,
            snapshot_hash=item.snapshot_hash,
            namespace=item.namespace,
            file_count=item.file_count,
            dependency_nodes=item.dependency_nodes,
            dependency_edges=item.dependency_edges,
        )

    def get(self, *, workspace_id: str, project_id: str) -> RepositoryIndexRecord | None:
        item = self.db.scalar(
            select(AgentRepositoryIndex).where(
                AgentRepositoryIndex.workspace_id == workspace_id,
                AgentRepositoryIndex.project_id == project_id,
            )
        )
        return None if item is None else self._record(item)

    def save(
        self,
        *,
        workspace_id: str,
        project_id: str,
        snapshot_hash: str,
        namespace: str,
        file_count: int,
        dependency_nodes: int,
        dependency_edges: int,
    ) -> RepositoryIndexRecord:
        item = self.db.scalar(
            select(AgentRepositoryIndex).where(
                AgentRepositoryIndex.workspace_id == workspace_id,
                AgentRepositoryIndex.project_id == project_id,
            )
        )
        if item is None:
            item = AgentRepositoryIndex(workspace_id=workspace_id, project_id=project_id)
            self.db.add(item)
        item.snapshot_hash = snapshot_hash
        item.namespace = namespace
        item.file_count = file_count
        item.dependency_nodes = dependency_nodes
        item.dependency_edges = dependency_edges
        self.db.flush()
        return self._record(item)
