from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .embedding import EmbeddingProvider, embedding_info
from .service import RetrievalChunk


LOCAL_HASH_SIMILARITY_CAP = 0.12


class PgVectorRagRepository:
    def __init__(self, engine: Engine, embedder: EmbeddingProvider) -> None:
        self.engine = engine
        self.embedder = embedder

    def embedding_info(self) -> dict[str, Any]:
        return embedding_info(self.embedder)

    def effective_threshold(self, configured_threshold: float) -> float:
        configured = max(0.0, min(1.0, float(configured_threshold)))
        info = self.embedding_info()
        if info.get("provider") == "local_hash":
            return min(configured, LOCAL_HASH_SIMILARITY_CAP)
        return configured

    def retrieve(
        self,
        *,
        organization_id: str,
        project_id: str,
        query: str,
        top_k: int,
        similarity_threshold: float,
    ) -> list[RetrievalChunk]:
        return self._search(
            organization_id=organization_id,
            project_id=project_id,
            query=query,
            top_k=top_k,
            similarity_threshold=float(similarity_threshold),
        )

    def retrieve_candidates(
        self,
        *,
        organization_id: str,
        project_id: str,
        query: str,
        top_k: int,
    ) -> list[RetrievalChunk]:
        return self._search(
            organization_id=organization_id,
            project_id=project_id,
            query=query,
            top_k=top_k,
            similarity_threshold=None,
        )

    def _search(
        self,
        *,
        organization_id: str,
        project_id: str,
        query: str,
        top_k: int,
        similarity_threshold: float | None,
    ) -> list[RetrievalChunk]:
        vector = self.embedder.embed(query)
        literal = "[" + ",".join(f"{value:.10f}" for value in vector) + "]"
        provider = self.embedding_info()
        signature = str(provider["signature"])
        threshold_clause = "" if similarity_threshold is None else "AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :threshold"
        statement = text(
            f"""
            SELECT c.id, d.source_type, d.source_id, d.source_path, c.content, c.metadata,
                   1 - (c.embedding <=> CAST(:embedding AS vector)) AS score
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.organization_id = :organization_id
              AND c.project_id = :project_id
              AND d.deleted_at IS NULL
              AND c.embedding IS NOT NULL
              AND (
                    c.metadata->>'embedding_signature' = :embedding_signature
                    OR NOT (c.metadata ? 'embedding_signature')
                  )
              {threshold_clause}
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """
        )
        params: dict[str, Any] = {
            "organization_id": organization_id,
            "project_id": project_id,
            "embedding": literal,
            "embedding_signature": signature,
            "limit": int(top_k),
        }
        if similarity_threshold is not None:
            params["threshold"] = float(similarity_threshold)
        with self.engine.connect() as connection:
            rows = connection.execute(statement, params).mappings().all()
        chunks: list[RetrievalChunk] = []
        for row in rows:
            metadata: Any = row["metadata"] or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}
            chunk_metadata = dict(metadata)
            chunk_metadata.setdefault("embedding_provider", provider.get("provider"))
            chunk_metadata.setdefault("embedding_model", provider.get("model"))
            chunk_metadata.setdefault("embedding_signature", signature)
            chunks.append(
                RetrievalChunk(
                    id=str(row["id"]),
                    source_type=str(row["source_type"]),
                    source_id=str(row["source_id"]) if row["source_id"] else None,
                    source_path=str(row["source_path"]) if row["source_path"] else None,
                    content=str(row["content"]),
                    score=float(row["score"] or 0.0),
                    metadata=chunk_metadata,
                )
            )
        return chunks

    def index_state(self, *, organization_id: str, project_id: str) -> dict[str, Any]:
        signature = str(self.embedding_info()["signature"])
        statement = text(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE c.metadata->>'embedding_signature' = :embedding_signature) AS compatible,
                COUNT(*) FILTER (WHERE NOT (c.metadata ? 'embedding_signature')) AS legacy,
                COUNT(*) FILTER (
                    WHERE c.metadata ? 'embedding_signature'
                      AND c.metadata->>'embedding_signature' <> :embedding_signature
                ) AS foreign
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE c.organization_id = :organization_id
              AND c.project_id = :project_id
              AND d.deleted_at IS NULL
              AND c.embedding IS NOT NULL
            """
        )
        with self.engine.connect() as connection:
            row = connection.execute(
                statement,
                {
                    "organization_id": organization_id,
                    "project_id": project_id,
                    "embedding_signature": signature,
                },
            ).mappings().one()
        total = int(row["total"] or 0)
        compatible = int(row["compatible"] or 0)
        legacy = int(row["legacy"] or 0)
        foreign = int(row["foreign"] or 0)
        return {
            "total_vectors": total,
            "compatible_vectors": compatible,
            "legacy_vectors": legacy,
            "foreign_vectors": foreign,
            "embedding_signature": signature,
            "reindex_required": total > 0 and compatible == 0 and legacy == 0 and foreign > 0,
        }

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
        provider = self.embedding_info()
        try:
            with self.engine.connect() as connection:
                extension = connection.execute(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                ).scalar_one()
            return {
                "status": "healthy" if extension else "degraded",
                "backend": "pgvector",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "embedding": provider,
            }
        except Exception as error:
            return {
                "status": "error",
                "backend": "pgvector",
                "detail": str(error)[:300],
                "embedding": provider,
            }
