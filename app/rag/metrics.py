from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


class RagMetricsService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def overview(self) -> dict[str, Any]:
        if self.engine.dialect.name != "postgresql":
            return self._empty()
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT
                  (SELECT COUNT(*) FROM rag_documents WHERE deleted_at IS NULL) AS documents,
                  (SELECT COUNT(*) FROM rag_chunks) AS chunks,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE status='pending') AS jobs_pending,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE status='processing') AS jobs_processing,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE status='failed') AS jobs_failed,
                  (SELECT COUNT(*) FROM rag_queries) AS queries_total,
                  (SELECT COUNT(*) FROM rag_queries WHERE cache_hit) AS cache_hits,
                  (SELECT COALESCE(AVG(retrieval_time_ms),0) FROM rag_queries) AS avg_retrieval_ms,
                  (SELECT COALESCE(SUM(retrieved_chunks),0) FROM rag_queries) AS chunks_retrieved
            """)).mappings().one()
        result = {key: (float(value) if key == "avg_retrieval_ms" else int(value or 0)) for key, value in row.items()}
        total = result["queries_total"]
        result["cache_hit_rate"] = round((result["cache_hits"] / total * 100.0) if total else 0.0, 2)
        return result

    def project(self, *, organization_id: str, project_id: str) -> dict[str, Any]:
        if self.engine.dialect.name != "postgresql":
            return {**self._empty(), "organization_id": organization_id, "project_id": project_id}
        params = {"organization_id": organization_id, "project_id": project_id}
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT
                  (SELECT COUNT(*) FROM rag_documents WHERE organization_id=:organization_id AND project_id=:project_id AND deleted_at IS NULL) AS documents,
                  (SELECT COUNT(*) FROM rag_chunks WHERE organization_id=:organization_id AND project_id=:project_id) AS chunks,
                  (SELECT COALESCE(SUM(token_count),0) FROM rag_chunks WHERE organization_id=:organization_id AND project_id=:project_id) AS indexed_tokens,
                  (SELECT COUNT(*) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS queries_total,
                  (SELECT COUNT(*) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id AND cache_hit) AS cache_hits,
                  (SELECT COALESCE(AVG(retrieval_time_ms),0) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS avg_retrieval_ms,
                  (SELECT COALESCE(SUM(retrieved_chunks),0) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS chunks_retrieved,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='pending') AS jobs_pending,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='processing') AS jobs_processing,
                  (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='failed') AS jobs_failed
            """), params).mappings().one()
        result = {key: (float(value) if key == "avg_retrieval_ms" else int(value or 0)) for key, value in row.items()}
        total = result["queries_total"]
        result["cache_hit_rate"] = round((result["cache_hits"] / total * 100.0) if total else 0.0, 2)
        result["organization_id"] = organization_id
        result["project_id"] = project_id
        return result

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "documents": 0,
            "chunks": 0,
            "indexed_tokens": 0,
            "jobs_pending": 0,
            "jobs_processing": 0,
            "jobs_failed": 0,
            "queries_total": 0,
            "cache_hits": 0,
            "cache_hit_rate": 0.0,
            "avg_retrieval_ms": 0.0,
            "chunks_retrieved": 0,
        }
