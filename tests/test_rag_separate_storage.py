from types import SimpleNamespace


def test_rag_engine_can_use_separate_database(monkeypatch, tmp_path):
    from app.rag import db as rag_db

    rag_db.get_rag_engine.cache_clear()
    rag_path = tmp_path / "rag.db"
    monkeypatch.setattr(
        rag_db,
        "get_settings",
        lambda: SimpleNamespace(
            rag_database_url=f"sqlite:///{rag_path}",
            database_url="sqlite:///./data/devpilot.db",
            rag_embedding_dimensions=1536,
        ),
    )

    engine = rag_db.get_rag_engine()
    try:
        assert engine.dialect.name == "sqlite"
        assert str(engine.url).endswith(str(rag_path))
    finally:
        engine.dispose()
        rag_db.get_rag_engine.cache_clear()


def test_rag_routes_keep_core_settings_and_vector_jobs_separate():
    from pathlib import Path

    source = Path("app/rag_admin_routes.py").read_text(encoding="utf-8")
    assert "engine as core_engine" in source
    assert "save_runtime_settings(core_engine, updated)" in source
    assert "enqueue_index_job(\n        get_rag_engine()," in source
    assert "list_jobs(get_rag_engine()" in source


def test_local_rag_setup_is_bound_to_loopback():
    from pathlib import Path

    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    script = Path("scripts/devpilot-rag-local-safe.sh").read_text(encoding="utf-8")
    assert '"127.0.0.1:5433:5432"' in compose
    assert "DEVPILOT_RAG_DATABASE_URL" in script
    assert "docker compose up -d postgres" in script
    assert "app.rag_worker_entry" in script
