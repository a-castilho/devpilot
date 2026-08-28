from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .embedding import EmbeddingProvider
from .service import RetrievalChunk


class PgVectorRagRepository:
    def __init__(self, engine: Engine, embedder: EmbeddingProvider) -> None:
        self.engine = engine
        self.embedder = embedder

    def retrieve(
        self,
        *,
        organization_id: str,
        project_id: str,
        query: str,
        top_k: int,
        similarity_threshold: float,
    ) -> list[RetrievalChunk]:
        vector = self.embedder.embed(query)
        literal = "[" + ",".join(f"{value:.10f}" for value in vector) + "]"
        statement = text(
            """
            SELECT c.id, d.source_type, d.source_id, d.source_path, c.content, c.metadata,
                   1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.organization_id = :organization_id
              AND c.project_id = :project_id
              AND d.deleted_at IS NULL
              AND c.embedding IS NOT NULL
              AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :threshold
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                statement,
                {
                    "organization_id": organization_id,
                    "project_id": project_id,
                    "embedding": literal,
                    "threshold": float(similarity_threshold),
                    "limit": int(top_k),
                },
            ).mappings().all()
        chunks: list[RetrievalChunk] = []
        for row in rows:
            metadata: Any = row["metadata"] or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            chunks.append(
                RetrievalChunk(
                    id=str(row["id"]),
                    source_type=str(row["source_type"]),
                    source_id=str(row["source_id"]) if row["source_id"] else None,
                    source_path=str(row["source_path"]) if row["source_path"] else None,
                    content=str(row["content"]),
                    score=float(row["score"] or 0.0),
                    metadata=dict(metadata),
                )
            )
        return chunks

    def record_query(
        self,
        *,
        organization_id: str,
        project_id: str,
        query: str,
        query_type: str,
        cache_hit: bool,
        retrieved_chunks: int,
        retrieval_time_ms: float,
    ) -> None:
        query_hash = hashlib.sha256(" ".join(query.lower().split()).encode("utf-8")).hexdigest()
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    text("""
                        INSERT INTO rag_queries
                        (id, organization_id, project_id, query_hash, query_type, cache_hit,
                         retrieved_chunks, retrieval_time_ms, embedding_time_ms, total_time_ms)
                        VALUES
                        (:id, :organization_id, :project_id, :query_hash, :query_type, :cache_hit,
                         :retrieved_chunks, :retrieval_time_ms, 0, :total_time_ms)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "organization_id": organization_id,
                        "project_id": project_id,
                        "query_hash": query_hash,
                        "query_type": query_type,
                        "cache_hit": bool(cache_hit),
                        "retrieved_chunks": int(retrieved_chunks),
                        "retrieval_time_ms": float(retrieval_time_ms),
                        "total_time_ms": float(retrieval_time_ms),
                    },
                )
        except Exception:
            # Telemetry must never break retrieval.
            return None

    def health(self) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            with self.engine.connect() as connection:
                extension = connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                ).scalar_one()
            return {
                "status": "healthy" if extension else "degraded",
                "backend": "pgvector",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except Exception as error:
            return {"status": "error", "backend": "pgvector", "detail": str(error)[:300]}
