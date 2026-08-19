from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


SourceKind = Literal["code", "docs", "config", "data", "other"]


@dataclass(frozen=True, slots=True)
class RepositoryDocument:
    path: str
    language: str
    kind: SourceKind
    content: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    project_id: str
    documents: tuple[RepositoryDocument, ...]
    snapshot_hash: str
    truncated: bool = False
    skipped_files: int = 0


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    source: str
    target: str
    relation: str = "imports"


@dataclass(frozen=True, slots=True)
class DependencyGraph:
    nodes: tuple[str, ...]
    edges: tuple[DependencyEdge, ...]

    def reverse_dependencies(self, path: str, *, depth: int = 2) -> list[str]:
        frontier = {path}
        visited = {path}
        impacted: list[str] = []
        for _ in range(max(0, depth)):
            next_frontier: set[str] = set()
            for edge in self.edges:
                if edge.target in frontier and edge.source not in visited:
                    visited.add(edge.source)
                    next_frontier.add(edge.source)
                    impacted.append(edge.source)
            if not next_frontier:
                break
            frontier = next_frontier
        return impacted


@dataclass(frozen=True, slots=True)
class RepositoryIndexRecord:
    project_id: str
    workspace_id: str
    snapshot_hash: str
    namespace: str
    file_count: int
    dependency_nodes: int
    dependency_edges: int


@dataclass(frozen=True, slots=True)
class ImpactReport:
    path: str
    impacted_files: tuple[str, ...] = field(default_factory=tuple)
    direct_dependencies: tuple[str, ...] = field(default_factory=tuple)
    depth: int = 2
