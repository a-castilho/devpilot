from pathlib import Path


def test_chat_route_uses_decoupled_knowledge_context():
    source = Path("app/chat_mode_routes.py").read_text(encoding="utf-8")
    assert "build_chat_knowledge_context" in source
    assert '"knowledge_mode": knowledge.mode.value' in source
    assert '"rag_sources": knowledge.sources' in source
    assert '"rag_used": bool(knowledge.sources)' in source


def test_build_mode_still_requires_approval():
    source = Path("app/chat_mode_routes.py").read_text(encoding="utf-8")
    assert "TaskStatus.awaiting_approval" in source
    assert '"requires_approval": True' in source
    assert "Tarefa de construção preparada e aguardando aprovação" in source


def test_chat_context_keeps_live_and_rag_separate():
    source = Path("app/rag/chat_context.py").read_text(encoding="utf-8")
    assert "RagQueryMode.LIVE" in source
    assert "RagQueryMode.RAG_LIVE" in source
    assert "Memória técnica recuperada pelo RAG" in source
    assert "Estado atual do" in source
    assert "organization_id=project.organization_id" in source
    assert "project_id=project.id" in source
