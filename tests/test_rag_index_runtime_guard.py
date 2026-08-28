import pytest
from fastapi import HTTPException

import app.rag_admin_routes as rag_routes


class _SqliteDialect:
    name = "sqlite"


class _SqliteEngine:
    dialect = _SqliteDialect()


def test_index_guard_rejects_runtime_without_rag_postgres(monkeypatch):
    monkeypatch.setattr(rag_routes, "rag_engine", None)

    with pytest.raises(HTTPException) as exc_info:
        rag_routes._require_index_backend()

    assert exc_info.value.status_code == 409
    assert "DEVPILOT_RAG_DATABASE_URL" in str(exc_info.value.detail)


def test_index_guard_rejects_non_postgres_rag_engine(monkeypatch):
    monkeypatch.setattr(rag_routes, "rag_engine", _SqliteEngine())

    with pytest.raises(HTTPException) as exc_info:
        rag_routes._require_index_backend()

    assert exc_info.value.status_code == 409
    assert "PostgreSQL/pgvector" in str(exc_info.value.detail)
