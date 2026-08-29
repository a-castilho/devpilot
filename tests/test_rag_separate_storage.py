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


def test_rag_routes_keep_runtime_settings_and_vector_jobs_on_rag_storage():
    from pathlib import Path

    routes = Path("app/rag_admin_routes.py").read_text(encoding="utf-8")
    runtime = Path("app/rag/runtime.py").read_text(encoding="utf-8")

    assert "engine as core_engine" not in routes
    assert "save_runtime_settings(get_rag_engine(), updated)" in routes
    assert "load_runtime_settings(get_rag_engine())" in runtime
    assert "load_runtime_settings(core_engine)" not in runtime
    assert "enqueue_index_job(\n        get_rag_engine()," in routes
    assert "list_jobs(get_rag_engine()" in routes


def test_local_rag_setup_is_bound_to_loopback_without_polluting_shared_env():
    from pathlib import Path

    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    script = Path("scripts/devpilot-rag-local-safe.sh").read_text(encoding="utf-8")
    rag_url = "DEVPILOT_RAG_DATABASE_URL: postgresql+psycopg://devpilot:devpilot@postgres:5432/devpilot"

    assert '"127.0.0.1:5433:5432"' in compose
    assert 'export DEVPILOT_RAG_DATABASE_URL="$RAG_URL"' in script
    assert "path.write_text" not in script
    assert "docker compose up -d postgres" in script
    assert "app.rag_worker_entry" in script
    assert compose.count(rag_url) == 3


def test_rag_reuses_general_openai_vault_credential_without_exposing_secret():
    from pathlib import Path

    runtime = Path("app/rag/runtime.py").read_text(encoding="utf-8")
    script = Path("scripts/devpilot-rag-local-safe.sh").read_text(encoding="utf-8")
    config = Path("app/config.py").read_text(encoding="utf-8")

    assert "ProviderCredential.provider == \"openai\"" in runtime
    assert "ProviderCredential.enabled.is_(True)" in runtime
    assert "Vault().decrypt(item.encrypted_secret)" in runtime
    assert "return _stored_openai_api_key()" in runtime
    assert "OPENAI_API_KEY" not in runtime
    assert "rag_embedding_api_key" not in runtime
    assert "rag_embedding_api_key" not in config
    assert "embedding_key_configured" in script


def test_local_hash_embeddings_are_deterministic_normalized_and_dimensioned():
    from app.rag.embedding import LocalHashEmbeddingProvider

    provider = LocalHashEmbeddingProvider(dimensions=64)
    first = provider.embed("DevPilot tarefas e projetos")
    second = provider.embed("DevPilot tarefas e projetos")

    assert first == second
    assert len(first) == 64
    assert any(value != 0.0 for value in first)
    assert abs(sum(value * value for value in first) - 1.0) < 1e-9


def test_local_hash_embeddings_preserve_lexical_similarity():
    from app.rag.embedding import LocalHashEmbeddingProvider

    provider = LocalHashEmbeddingProvider(dimensions=256)
    base = provider.embed("fila de tarefas do projeto devpilot")
    related = provider.embed("tarefas do projeto devpilot na fila")
    unrelated = provider.embed("receita de bolo com chocolate")

    def dot(left, right):
        return sum(a * b for a, b in zip(left, right, strict=True))

    assert dot(base, related) > dot(base, unrelated)


def test_runtime_falls_back_to_local_embeddings_without_api_key():
    from pathlib import Path

    runtime = Path("app/rag/runtime.py").read_text(encoding="utf-8")
    script = Path("scripts/devpilot-rag-local-safe.sh").read_text(encoding="utf-8")

    assert "LocalHashEmbeddingProvider" in runtime
    assert "return LocalHashEmbeddingProvider" in runtime
    assert "fallback local CPU-only" in script
    assert "nenhuma credencial OpenAI disponível" not in script


def test_rag_feature_branch_restart_does_not_merge_main_into_checkout():
    from pathlib import Path

    rag_script = Path("scripts/devpilot-rag-local-safe.sh").read_text(encoding="utf-8")
    safe_script = Path("scripts/devpilot-local-safe.sh").read_text(encoding="utf-8")

    assert "DEVPILOT_SAFE_SKIP_UPDATE=1 bash scripts/devpilot-local-safe.sh" in rag_script
    assert 'DEVPILOT_SAFE_SKIP_UPDATE:-0' in safe_script
    assert 'VALIDATION_BASE="${DEVPILOT_SAFE_VALIDATION_BASE:-origin/main}"' in safe_script
    assert 'git merge --ff-only origin/main' in safe_script


def test_rag_worker_retries_transient_storage_failures():
    from pathlib import Path

    source = Path("app/rag_worker_entry.py").read_text(encoding="utf-8")
    assert "except (SQLAlchemyError, OSError, RuntimeError)" in source
    assert "falha transitória" in source
    assert "time.sleep(RETRY_DELAY_SECONDS)" in source
