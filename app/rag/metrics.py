from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


class RagMetricsService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def _serialize_row(row: Any) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in row.items():
            if key == "avg_retrieval_ms":
                result[key] = float(value or 0.0)
            elif key in {"last_indexed_at", "last_query_at", "last_job_at"}:
                result[key] = value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)
            else:
                result[key] = int(value or 0)
        total = int(result.get("queries_total") or 0)
        cache_hits = int(result.get("cache_hits") or 0)
        result["cache_hit_rate"] = round((cache_hits / total * 100.0) if total else 0.0, 2)
        return result

    def overview(self) -> dict[str, Any]:
        if self.engine.dialect.name != "postgresql":
            return self._empty()
        try:
            with self.engine.connect() as connection:
                row = connection.execute(text("""
                    SELECT
                      (SELECT COUNT(*) FROM rag_documents WHERE deleted_at IS NULL) AS documents,
                      (SELECT COUNT(DISTINCT project_id) FROM rag_documents WHERE deleted_at IS NULL) AS indexed_projects,
                      (SELECT COUNT(*) FROM rag_chunks) AS chunks,
                      (SELECT COALESCE(SUM(token_count),0) FROM rag_chunks) AS indexed_tokens,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE status='pending') AS jobs_pending,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE status='processing') AS jobs_processing,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE status='completed') AS jobs_completed,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE status='failed') AS jobs_failed,
                      (SELECT COUNT(*) FROM rag_queries) AS queries_total,
                      (SELECT COUNT(*) FROM rag_queries WHERE cache_hit) AS cache_hits,
                      (SELECT COALESCE(AVG(retrieval_time_ms),0) FROM rag_queries) AS avg_retrieval_ms,
                      (SELECT COALESCE(SUM(retrieved_chunks),0) FROM rag_queries) AS chunks_retrieved,
                      (SELECT MAX(indexed_at) FROM rag_documents WHERE deleted_at IS NULL) AS last_indexed_at,
                      (SELECT MAX(created_at) FROM rag_queries) AS last_query_at,
                      (SELECT MAX(created_at) FROM rag_index_jobs) AS last_job_at
                """)).mappings().one()
        except SQLAlchemyError:
            return self._empty()
        return self._serialize_row(row)

    def project(self, *, organization_id: str, project_id: str) -> dict[str, Any]:
        if self.engine.dialect.name != "postgresql":
            return {**self._empty(), "organization_id": organization_id, "project_id": project_id}
        params = {"organization_id": organization_id, "project_id": project_id}
        try:
            with self.engine.connect() as connection:
                row = connection.execute(text("""
                    SELECT
                      (SELECT COUNT(*) FROM rag_documents WHERE organization_id=:organization_id AND project_id=:project_id AND deleted_at IS NULL) AS documents,
                      (SELECT CASE WHEN EXISTS(
                          SELECT 1 FROM rag_documents WHERE organization_id=:organization_id AND project_id=:project_id AND deleted_at IS NULL
                       ) THEN 1 ELSE 0 END) AS indexed_projects,
                      (SELECT COUNT(*) FROM rag_chunks WHERE organization_id=:organization_id AND project_id=:project_id) AS chunks,
                      (SELECT COALESCE(SUM(token_count),0) FROM rag_chunks WHERE organization_id=:organization_id AND project_id=:project_id) AS indexed_tokens,
                      (SELECT COUNT(*) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS queries_total,
                      (SELECT COUNT(*) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id AND cache_hit) AS cache_hits,
                      (SELECT COALESCE(AVG(retrieval_time_ms),0) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS avg_retrieval_ms,
                      (SELECT COALESCE(SUM(retrieved_chunks),0) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS chunks_retrieved,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='pending') AS jobs_pending,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='processing') AS jobs_processing,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='completed') AS jobs_completed,
                      (SELECT COUNT(*) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id AND status='failed') AS jobs_failed,
                      (SELECT MAX(indexed_at) FROM rag_documents WHERE organization_id=:organization_id AND project_id=:project_id AND deleted_at IS NULL) AS last_indexed_at,
                      (SELECT MAX(created_at) FROM rag_queries WHERE organization_id=:organization_id AND project_id=:project_id) AS last_query_at,
                      (SELECT MAX(created_at) FROM rag_index_jobs WHERE organization_id=:organization_id AND project_id=:project_id) AS last_job_at
                """), params).mappings().one()
        except SQLAlchemyError:
            return {**self._empty(), "organization_id": organization_id, "project_id": project_id}
        result = self._serialize_row(row)
        result["organization_id"] = organization_id
        result["project_id"] = project_id
        return result

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "documents": 0,
            "indexed_projects": 0,
            "chunks": 0,
            "indexed_tokens": 0,
            "jobs_pending": 0,
            "jobs_processing": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "queries_total": 0,
            "cache_hits": 0,
            "cache_hit_rate": 0.0,
            "avg_retrieval_ms": 0.0,
            "chunks_retrieved": 0,
            "last_indexed_at": None,
            "last_query_at": None,
            "last_job_at": None,
        }
