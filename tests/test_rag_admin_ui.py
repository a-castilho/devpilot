from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine

import app.rag_admin_routes as rag_routes


ROOT = Path(__file__).resolve().parents[1]


def test_rag_admin_ui_is_lazy_loaded_with_super_admin_bundle():
    loader = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
    assert "rag-admin-ui.js" in loader
    assert "admin:" in loader


def test_rag_admin_ui_uses_super_admin_rag_endpoints():
    ui = (ROOT / "app/static/rag-admin-ui.js").read_text(encoding="utf-8")
    assert "/super-admin/rag/overview" in ui
    assert "/super-admin/rag/settings" in ui
    assert "/super-admin/rag/health" in ui
    assert "/super-admin/rag/projects/" in ui
    assert "RAG / Conhecimento" in ui


def test_rag_jobs_ui_renders_storage_unavailable_as_neutral_state():
    ui = (ROOT / "app/static/rag-jobs-ui.js").read_text(encoding="utf-8")
    assert "payload?.available === false" in ui
    assert "renderUnavailable(payload.message)" in ui
    assert "RAG indisponível neste ambiente." in ui


def _unexpected_rag_sql(*args, **kwargs):
    raise AssertionError("RAG SQL must not execute when the runtime engine is SQLite")


def test_rag_jobs_route_returns_degraded_payload_on_sqlite_without_rag_sql(monkeypatch):
    sqlite_engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(rag_routes, "engine", sqlite_engine)
    monkeypatch.setattr(rag_routes, "list_jobs", _unexpected_rag_sql)

    payload = rag_routes.jobs(project_id="project-1", limit=20)

    assert payload == {
        "available": False,
        "reason": "postgresql_required",
        "message": rag_routes.RAG_STORAGE_UNAVAILABLE_MESSAGE,
        "jobs": [],
    }


def test_rag_index_route_returns_503_on_sqlite_without_enqueue_sql(monkeypatch):
    sqlite_engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(rag_routes, "engine", sqlite_engine)
    monkeypatch.setattr(rag_routes, "enqueue_index_job", _unexpected_rag_sql)

    project = SimpleNamespace(id="project-1", organization_id="org-1")
    db = SimpleNamespace(scalar=lambda statement: project)
    principal = SimpleNamespace(workspace_id="workspace-1", actor="user:test")

    with pytest.raises(HTTPException) as exc_info:
        rag_routes.index_project("project-1", db=db, principal=principal)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == rag_routes.RAG_STORAGE_UNAVAILABLE_MESSAGE


def test_rag_retry_route_returns_503_on_sqlite_without_retry_sql(monkeypatch):
    sqlite_engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(rag_routes, "engine", sqlite_engine)
    monkeypatch.setattr(rag_routes, "retry_job", _unexpected_rag_sql)

    db = SimpleNamespace()
    principal = SimpleNamespace(workspace_id="workspace-1", actor="user:test")

    with pytest.raises(HTTPException) as exc_info:
        rag_routes.retry("job-1", db=db, principal=principal)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == rag_routes.RAG_STORAGE_UNAVAILABLE_MESSAGE
