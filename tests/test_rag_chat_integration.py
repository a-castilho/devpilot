from pathlib import Path


def test_chat_route_uses_decoupled_knowledge_context():
    source = Path("app/chat_mode_routes.py").read_text(encoding="utf-8")
    assert "build_chat_knowledge_context" in source
    assert '"knowledge_mode": knowledge.mode.value' in source
    assert '"rag_sources": knowledge.sources' in source
    assert '"rag_used": bool(knowledge.sources)' in source


def test_build_mode_uses_approval_by_exception():
    source = Path("app/chat_mode_routes.py").read_text(encoding="utf-8")
    assert "decision = evaluate_task(prompt, False)" in source
    assert "TaskStatus.awaiting_approval if decision.requires_approval else TaskStatus.queued" in source
    assert '"requires_approval": decision.requires_approval' in source
    assert "Tarefa de construção enfileirada automaticamente para execução." in source
    assert "política identificou um limite de alto risco" in source


def test_chat_context_keeps_live_and_rag_separate():
    source = Path("app/rag/chat_context.py").read_text(encoding="utf-8")
    assert "RagQueryMode.LIVE" in source
    assert "RagQueryMode.RAG_LIVE" in source
    assert "Memória técnica recuperada pelo RAG" in source
    assert "Estado atual do" in source
    assert "organization_id=project.organization_id" in source
    assert "project_id=project.id" in source


def test_chat_context_degrades_when_rag_retrieval_fails():
    source = Path("app/rag/chat_context.py").read_text(encoding="utf-8")
    assert "except Exception as exc" in source
    assert "RAG retrieval unavailable" in source
    assert "o chat continua sem contexto histórico adicional" in source


def test_compose_enables_rag_for_chat_runtime():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")
    app_section = source.split("\n  app:\n", 1)[1].split("\n  cloudflared:\n", 1)[0]
    assert 'DEVPILOT_RAG_ENABLED: "true"' in app_section
    assert "DEVPILOT_RAG_DATABASE_URL:" in app_section
    assert "DEVPILOT_REDIS_URL:" in app_section


def test_compose_runs_single_rag_index_worker():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert source.count("\n  rag-worker:\n") == 1
    rag_worker = source.split("\n  rag-worker:\n", 1)[1].split("\n  postgres:\n", 1)[0]
    assert 'command: ["python", "-m", "app.rag_worker_entry"]' in rag_worker
    assert 'DEVPILOT_RAG_ENABLED: "true"' in rag_worker
    assert "DEVPILOT_RAG_DATABASE_URL:" in rag_worker
