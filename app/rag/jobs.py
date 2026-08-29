from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


MAX_ATTEMPTS = 3


def enqueue_index_job(engine: Engine, *, organization_id: str, project_id: str, source_type: str = "project") -> dict:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        existing = connection.execute(
            text("""
                SELECT id, status FROM rag_index_jobs
                WHERE organization_id=:organization_id AND project_id=:project_id
                  AND status IN ('pending','processing')
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"organization_id": organization_id, "project_id": project_id},
        ).mappings().first()
        if existing:
            return {"id": existing["id"], "status": existing["status"], "created": False}
        connection.execute(
            text("""
                INSERT INTO rag_index_jobs
                (id, organization_id, project_id, source_type, status, attempts, created_at, progress_done, progress_total)
                VALUES (:id,:organization_id,:project_id,:source_type,'pending',0,:created_at,0,0)
            """),
            {
                "id": job_id,
                "organization_id": organization_id,
                "project_id": project_id,
                "source_type": source_type,
                "created_at": now,
            },
        )
    return {"id": job_id, "status": "pending", "created": True}


def list_jobs(engine: Engine, *, project_id: str | None = None, limit: int = 50) -> list[dict]:
    """Read the optional RAG queue without making monitoring a core dependency."""
    if engine.dialect.name != "postgresql":
        return []

    clauses = []
    params: dict = {"limit": max(1, min(int(limit), 100))}
    if project_id:
        clauses.append("project_id=:project_id")
        params["project_id"] = project_id
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        with engine.begin() as connection:
            rows = connection.execute(
                text(f"""
                    SELECT id, organization_id, project_id, source_type, source_id, status, attempts,
                           last_error, started_at, completed_at, created_at, progress_done, progress_total,
                           indexed_files, skipped_files, failed_files, chunks_indexed
                    FROM rag_index_jobs
                    {where}
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                params,
            ).mappings().all()
    except SQLAlchemyError:
        return []
    return [dict(row) for row in rows]


def retry_job(engine: Engine, job_id: str) -> dict | None:
    with engine.begin() as connection:
        row = connection.execute(
            text("""
                UPDATE rag_index_jobs
                SET status='pending', last_error=NULL, started_at=NULL, completed_at=NULL,
                    progress_done=0, indexed_files=0, skipped_files=0, failed_files=0, chunks_indexed=0
                WHERE id=:id AND status='failed' AND attempts < :max_attempts
                RETURNING id, project_id, status, attempts
            """),
            {"id": job_id, "max_attempts": MAX_ATTEMPTS},
        ).mappings().first()
    return dict(row) if row else None


def claim_next_job(engine: Engine) -> dict | None:
    with engine.begin() as connection:
        row = connection.execute(
            text("""
                SELECT id, organization_id, project_id, source_type, attempts
                FROM rag_index_jobs
                WHERE status='pending' AND attempts < :max_attempts
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """),
            {"max_attempts": MAX_ATTEMPTS},
        ).mappings().first()
        if not row:
            return None
        connection.execute(
            text("""
                UPDATE rag_index_jobs
                SET status='processing', attempts=attempts+1, started_at=NOW(), completed_at=NULL, last_error=NULL,
                    indexed_files=0, skipped_files=0, failed_files=0, chunks_indexed=0
                WHERE id=:id
            """),
            {"id": row["id"]},
        )
    result = dict(row)
    result["attempts"] = int(result.get("attempts") or 0) + 1
    return result


def update_progress(engine: Engine, job_id: str, *, done: int, total: int) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE rag_index_jobs SET progress_done=:done, progress_total=:total WHERE id=:id"),
            {"id": job_id, "done": max(0, int(done)), "total": max(0, int(total))},
        )


def _result_stats(result: dict | None) -> dict[str, int]:
    result = result or {}
    return {
        "indexed": max(0, int(result.get("indexed") or 0)),
        "skipped": max(0, int(result.get("skipped") or 0)),
        "failed": max(0, int(result.get("failed") or 0)),
        "chunks": max(0, int(result.get("chunks_indexed") or 0)),
    }


def complete_job(engine: Engine, job_id: str, *, result: dict | None = None) -> None:
    stats = _result_stats(result)
    with engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE rag_index_jobs
                SET status='completed', completed_at=NOW(), last_error=NULL,
                    indexed_files=:indexed, skipped_files=:skipped, failed_files=:failed, chunks_indexed=:chunks
                WHERE id=:id
            """),
            {"id": job_id, **stats},
        )


def fail_job(engine: Engine, job_id: str, error: str, *, result: dict | None = None) -> None:
    message = str(error or "RAG indexing failed")[-4000:]
    stats = _result_stats(result)
    with engine.begin() as connection:
        attempts = connection.execute(
            text("SELECT attempts FROM rag_index_jobs WHERE id=:id"), {"id": job_id}
        ).scalar_one_or_none()
        status = "failed" if int(attempts or 0) >= MAX_ATTEMPTS else "pending"
        connection.execute(
            text("""
                UPDATE rag_index_jobs
                SET status=:status, last_error=:error,
                    completed_at=CASE WHEN :status='failed' THEN NOW() ELSE NULL END,
                    indexed_files=:indexed, skipped_files=:skipped, failed_files=:failed, chunks_indexed=:chunks
                WHERE id=:id
            """),
            {"id": job_id, "status": status, "error": message, **stats},
        )
