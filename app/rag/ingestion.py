from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.models import Project
from .chunking import RagChunker
from .embedding import EmbeddingProvider, embedding_info
from .git_source import GitRagSource
from .sanitizer import RagSanitizer


class RagIndexer:
    def __init__(self, engine: Engine, embedder: EmbeddingProvider, *, chunk_size: int = 500, overlap: int = 50) -> None:
        self.engine = engine
        self.embedder = embedder
        self.chunker = RagChunker(chunk_size=chunk_size, overlap=overlap)
        self.sanitizer = RagSanitizer()
        self.source = GitRagSource()

    def index_project(self, project: Project, progress: Callable[[int, int], None] | None = None) -> dict:
        if not project.organization_id:
            raise ValueError("Project must belong to an organization before RAG indexing")
        indexed = 0
        skipped = 0
        failed = 0
        chunks_indexed = 0
        errors: list[str] = []
        paths = self.source.list_files(project)
        total = len(paths)
        if progress:
            progress(0, total)
        for position, path in enumerate(paths, start=1):
            try:
                changed, chunk_count = self._index_file_with_stats(project, path)
                indexed += 1 if changed else 0
                skipped += 0 if changed else 1
                chunks_indexed += chunk_count
            except Exception as error:
                failed += 1
                if len(errors) < 10:
                    errors.append(f"{path}: {str(error)[:300]}")
            if progress:
                progress(position, total)
        return {
            "project_id": project.id,
            "indexed": indexed,
            "skipped": skipped,
            "failed": failed,
            "chunks_indexed": chunks_indexed,
            "total": total,
            "errors": errors,
        }

    def index_file(self, project: Project, path: str) -> bool:
        changed, _ = self._index_file_with_stats(project, path)
        return changed

    def _index_file_with_stats(self, project: Project, path: str) -> tuple[bool, int]:
        raw = self.source.read(project, path)
        content = self.sanitizer.sanitize(raw)
        if not content.strip():
            return False, 0
        provider = embedding_info(self.embedder)
        signature = str(provider["signature"])
        digest = hashlib.sha256(f"{signature}\n{content}".encode("utf-8")).hexdigest()
        source_type = "documentation" if path.lower().endswith((".md", ".txt")) or path.startswith("docs/") else "git_file"
        with self.engine.begin() as connection:
            existing = connection.execute(
                text("""
                    SELECT id FROM rag_documents
                    WHERE organization_id=:organization_id AND project_id=:project_id
                      AND source_type=:source_type AND source_id=:source_id
                      AND content_hash=:content_hash AND deleted_at IS NULL
                    LIMIT 1
                """),
                {
                    "organization_id": project.organization_id,
                    "project_id": project.id,
                    "source_type": source_type,
                    "source_id": path,
                    "content_hash": digest,
                },
            ).scalar_one_or_none()
            if existing:
                return False, 0

            connection.execute(
                text("""
                    UPDATE rag_documents SET deleted_at=NOW(), updated_at=NOW()
                    WHERE organization_id=:organization_id AND project_id=:project_id
                      AND source_type=:source_type AND source_id=:source_id AND deleted_at IS NULL
                """),
                {"organization_id": project.organization_id, "project_id": project.id, "source_type": source_type, "source_id": path},
            )
            document_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            document_metadata = {
                "repository_url": project.repository_url,
                "branch": project.default_branch,
                "embedding_provider": provider.get("provider"),
                "embedding_model": provider.get("model"),
                "embedding_dimensions": provider.get("dimensions"),
                "embedding_signature": signature,
            }
            connection.execute(
                text("""
                    INSERT INTO rag_documents
                    (id, organization_id, project_id, source_type, source_id, source_path, title, content_hash, version, metadata, indexed_at, created_at, updated_at)
                    VALUES (:id,:organization_id,:project_id,:source_type,:source_id,:source_path,:title,:content_hash,:version,CAST(:metadata AS jsonb),:indexed_at,:created_at,:updated_at)
                """),
                {
                    "id": document_id,
                    "organization_id": project.organization_id,
                    "project_id": project.id,
                    "source_type": source_type,
                    "source_id": path,
                    "source_path": path,
                    "title": path,
                    "content_hash": digest,
                    "version": project.default_branch,
                    "metadata": json.dumps(document_metadata),
                    "indexed_at": now,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            chunks = self.chunker.split(content)
            for chunk in chunks:
                vector = self.embedder.embed(chunk.content)
                literal = "[" + ",".join(f"{value:.10f}" for value in vector) + "]"
                chunk_metadata = {
                    "path": path,
                    "embedding_provider": provider.get("provider"),
                    "embedding_model": provider.get("model"),
                    "embedding_dimensions": provider.get("dimensions"),
                    "embedding_signature": signature,
                }
                connection.execute(
                    text("""
                        INSERT INTO rag_chunks
                        (id, document_id, organization_id, project_id, chunk_index, content, embedding, token_count, metadata)
                        VALUES (:id,:document_id,:organization_id,:project_id,:chunk_index,:content,CAST(:embedding AS vector),:token_count,CAST(:metadata AS jsonb))
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "organization_id": project.organization_id,
                        "project_id": project.id,
                        "chunk_index": chunk.index,
                        "content": chunk.content,
                        "embedding": literal,
                        "token_count": len(chunk.content.split()),
                        "metadata": json.dumps(chunk_metadata),
                    },
                )
        return True, len(chunks)
