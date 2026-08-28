from sqlalchemy.exc import OperationalError

from app.rag.jobs import list_jobs
from app.rag.schema import ensure_rag_schema


class _Dialect:
    name = "postgresql"


class _BrokenEngine:
    dialect = _Dialect()

    def begin(self):
        raise OperationalError("CREATE EXTENSION vector", {}, RuntimeError("pgvector unavailable"))


def test_rag_schema_failure_does_not_escape_bootstrap():
    assert ensure_rag_schema(_BrokenEngine(), embedding_dimensions=1536) is False


class _SqliteDialect:
    name = "sqlite"


class _SqliteEngine:
    dialect = _SqliteDialect()

    def begin(self):
        raise AssertionError("SQLite must not query the PostgreSQL-only RAG queue")


def test_rag_schema_is_skipped_outside_postgres():
    assert ensure_rag_schema(_SqliteEngine(), embedding_dimensions=1536) is False


def test_rag_job_list_is_empty_outside_postgres_without_touching_schema():
    assert list_jobs(_SqliteEngine(), project_id="project-1", limit=20) == []
