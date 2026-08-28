from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rag_storage_is_decoupled_from_core_database():
    config = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
    database = (ROOT / "app" / "rag" / "database.py").read_text(encoding="utf-8")
    runtime = (ROOT / "app" / "rag" / "runtime.py").read_text(encoding="utf-8")
    worker = (ROOT / "app" / "rag" / "worker.py").read_text(encoding="utf-8")

    assert 'rag_database_url: str = ""' in config
    assert "settings.rag_database_url.strip()" in database
    assert 'if settings.database_url.startswith("postgresql")' in database
    assert "PgVectorRagRepository(rag_engine, embedder)" in runtime
    assert "claim_next_job(rag_engine)" in worker
    assert "RagIndexer(\n            rag_engine," in worker


def test_local_rag_sidecar_is_loopback_only_and_uses_safe_restart():
    compose = (ROOT / "docker-compose.rag-local.yml").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "devpilot-rag-local.sh").read_text(encoding="utf-8")

    assert '"127.0.0.1:55432:5432"' in compose
    assert '"127.0.0.1:56379:6379"' in compose
    assert '"--maxmemory", "96mb"' in compose
    assert "pkill" not in script
    assert 'bash "$ROOT/scripts/devpilot-local-safe.sh"' in script
    assert "-m app.rag_worker_entry" in script
    assert "get_rag_embedder() is not None" in script


def test_rag_admin_routes_use_vector_storage_without_moving_core_projects():
    routes = (ROOT / "app" / "rag_admin_routes.py").read_text(encoding="utf-8")

    assert "return rag_engine or engine" in routes
    assert "storage_engine = _require_index_backend()" in routes
    assert "enqueue_index_job(\n        storage_engine," in routes
    assert "db.scalar(select(Project).where(Project.id == project_id))" in routes
