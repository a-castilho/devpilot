from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from app.agentos.application.ports import EventBusPort, KnowledgePort, UnitOfWorkPort
from app.agentos.domain.events import DomainEvent
from app.agentos.domain.intelligence import (
    DependencyGraph,
    ImpactReport,
    RepositoryIndexRecord,
    RepositorySnapshot,
)


class RepositorySnapshotPort(Protocol):
    def snapshot(self, *, project_id: str, refresh: bool = False) -> RepositorySnapshot: ...

    def graph(self, snapshot: RepositorySnapshot) -> DependencyGraph: ...


class RepositoryIndexPort(Protocol):
    def get(self, *, workspace_id: str, project_id: str) -> RepositoryIndexRecord | None: ...

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
    ) -> RepositoryIndexRecord: ...


class RepositoryIntelligenceService:
    def __init__(
        self,
        *,
        snapshots: RepositorySnapshotPort,
        indexes: RepositoryIndexPort,
        knowledge: KnowledgePort,
        events: EventBusPort,
        uow: UnitOfWorkPort,
    ) -> None:
        self.snapshots = snapshots
        self.indexes = indexes
        self.knowledge = knowledge
        self.events = events
        self.uow = uow

    def status(self, *, workspace_id: str, project_id: str) -> RepositoryIndexRecord | None:
        return self.indexes.get(workspace_id=workspace_id, project_id=project_id)

    def index_project(
        self,
        *,
        workspace_id: str,
        project_id: str,
        refresh: bool = False,
    ) -> dict[str, Any]:
        snapshot = self.snapshots.snapshot(project_id=project_id, refresh=refresh)
        current = self.indexes.get(workspace_id=workspace_id, project_id=project_id)
        if current and current.snapshot_hash == snapshot.snapshot_hash:
            return {
                "indexed": False,
                "reason": "unchanged",
                "index": asdict(current),
                "truncated": snapshot.truncated,
                "skipped_files": snapshot.skipped_files,
            }

        graph = self.snapshots.graph(snapshot)
        namespace = f"repo/{project_id}/{snapshot.snapshot_hash[:16]}"
        try:
            for document in snapshot.documents:
                self.knowledge.ingest(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    namespace=namespace,
                    source=f"repo://{project_id}/{document.path}",
                    content=f"Path: {document.path}\nLanguage: {document.language}\n\n{document.content}",
                    metadata={
                        "kind": "repository-document",
                        "path": document.path,
                        "language": document.language,
                        "source_kind": document.kind,
                        "content_hash": document.content_hash,
                        "snapshot_hash": snapshot.snapshot_hash,
                    },
                )

            manifest = "\n".join(
                [
                    f"Repository snapshot: {snapshot.snapshot_hash}",
                    f"Files indexed: {len(snapshot.documents)}",
                    f"Dependency nodes: {len(graph.nodes)}",
                    f"Dependency edges: {len(graph.edges)}",
                    "Dependencies:",
                    *[
                        f"- {edge.source} -> {edge.target} ({edge.relation})"
                        for edge in graph.edges[:1000]
                    ],
                ]
            )
            self.knowledge.ingest(
                workspace_id=workspace_id,
                project_id=project_id,
                namespace=namespace,
                source=f"repo://{project_id}/.agentos/manifest",
                content=manifest,
                metadata={
                    "kind": "repository-manifest",
                    "snapshot_hash": snapshot.snapshot_hash,
                },
            )
            record = self.indexes.save(
                workspace_id=workspace_id,
                project_id=project_id,
                snapshot_hash=snapshot.snapshot_hash,
                namespace=namespace,
                file_count=len(snapshot.documents),
                dependency_nodes=len(graph.nodes),
                dependency_edges=len(graph.edges),
            )
            self.events.publish(
                DomainEvent(
                    name="agentos.repository.indexed",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    payload={
                        "snapshot_hash": snapshot.snapshot_hash,
                        "namespace": namespace,
                        "file_count": len(snapshot.documents),
                        "dependency_nodes": len(graph.nodes),
                        "dependency_edges": len(graph.edges),
                        "truncated": snapshot.truncated,
                        "skipped_files": snapshot.skipped_files,
                    },
                )
            )
            self.uow.commit()
            return {
                "indexed": True,
                "index": asdict(record),
                "truncated": snapshot.truncated,
                "skipped_files": snapshot.skipped_files,
            }
        except Exception:
            self.uow.rollback()
            raise

    def search(
        self,
        *,
        workspace_id: str,
        project_id: str,
        query: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        current = self.indexes.get(workspace_id=workspace_id, project_id=project_id)
        if current is None:
            return []
        return self.knowledge.search(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=current.namespace,
            query=query,
            top_k=top_k,
        )

    def impact(
        self,
        *,
        project_id: str,
        path: str,
        depth: int = 2,
        refresh: bool = False,
    ) -> ImpactReport:
        snapshot = self.snapshots.snapshot(project_id=project_id, refresh=refresh)
        graph = self.snapshots.graph(snapshot)
        normalized = path.strip().lstrip("./")
        direct = tuple(
            edge.target for edge in graph.edges if edge.source == normalized
        )
        impacted = tuple(graph.reverse_dependencies(normalized, depth=depth))
        return ImpactReport(
            path=normalized,
            impacted_files=impacted,
            direct_dependencies=direct,
            depth=depth,
        )
