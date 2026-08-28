from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_rag_schema(engine: Engine, *, embedding_dimensions: int = 1536) -> None:
    """Create/evolve the additive RAG schema without making DEVpilot depend on it."""
    if engine.dialect.name != "postgresql":
        return
    dimensions = int(embedding_dimensions)
    if dimensions < 256 or dimensions > 4096:
        raise ValueError("embedding_dimensions must be between 256 and 4096")

    statements = [
        "CREATE EXTENSION IF NOT EXISTS vector",
        """
        CREATE TABLE IF NOT EXISTS rag_runtime_settings (
            key VARCHAR(40) PRIMARY KEY,
            value JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rag_documents (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            project_id VARCHAR(36) NOT NULL,
            source_type VARCHAR(40) NOT NULL,
            source_id VARCHAR(255),
            source_path TEXT,
            title TEXT,
            content_hash VARCHAR(64) NOT NULL,
            version VARCHAR(120),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            indexed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            deleted_at TIMESTAMPTZ
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_rag_documents_scope ON rag_documents (organization_id, project_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_rag_documents_source_hash ON rag_documents (organization_id, project_id, source_type, source_id, content_hash)",
        f"""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id VARCHAR(36) PRIMARY KEY,
            document_id VARCHAR(36) NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
            organization_id VARCHAR(36) NOT NULL,
            project_id VARCHAR(36) NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector({dimensions}),
            token_count INTEGER NOT NULL DEFAULT 0,
            metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(document_id, chunk_index)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_rag_chunks_scope ON rag_chunks (organization_id, project_id)",
        """
        CREATE TABLE IF NOT EXISTS rag_index_jobs (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            project_id VARCHAR(36) NOT NULL,
            source_type VARCHAR(40) NOT NULL,
            source_id VARCHAR(255),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            progress_done INTEGER NOT NULL DEFAULT 0,
            progress_total INTEGER NOT NULL DEFAULT 0
        )
        """,
        "ALTER TABLE rag_index_jobs ADD COLUMN IF NOT EXISTS progress_done INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE rag_index_jobs ADD COLUMN IF NOT EXISTS progress_total INTEGER NOT NULL DEFAULT 0",
        "CREATE INDEX IF NOT EXISTS ix_rag_jobs_scope_status ON rag_index_jobs (organization_id, project_id, status)",
        """
        CREATE TABLE IF NOT EXISTS rag_queries (
            id VARCHAR(36) PRIMARY KEY,
            organization_id VARCHAR(36) NOT NULL,
            project_id VARCHAR(36) NOT NULL,
            query_hash VARCHAR(64) NOT NULL,
            query_type VARCHAR(20) NOT NULL,
            cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
            retrieved_chunks INTEGER NOT NULL DEFAULT 0,
            retrieval_time_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
            embedding_time_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
            total_time_ms DOUBLE PRECISION NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_rag_queries_scope_created ON rag_queries (organization_id, project_id, created_at DESC)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
