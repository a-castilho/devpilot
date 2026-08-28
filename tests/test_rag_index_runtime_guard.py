import pytest
from fastapi import HTTPException

import app.rag_admin_routes as rag_routes


class _SqliteDialect:
    name = "sqlite"


class _SqliteEngine:
    dialect = _SqliteDialect()


def test_index_guard_rejects_runtime_without_postgres(monkeypatch):
    monkeypatch.setattr(rag_routes, "engine", _SqliteEngine())

    with pytest.raises(HTTPException) as exc_info:
        rag_routes._require_index_backend()

    assert exc_info.value.status_code == 409
    assert "PostgreSQL com pgvector" in str(exc_info.value.detail)
