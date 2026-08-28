from app.rag.admin import RagAdminService
from app.rag.chunking import RagChunker
from app.rag.sanitizer import RagSanitizer
from app.rag.service import RagQueryMode, RagQueryRouter, RagService, RagSettings


def test_rag_disabled_is_safe_default():
    service = RagService()
    result = service.retrieve(organization_id="org-1", project_id="project-1", query="arquitetura")
    assert result.chunks == []
    assert result.mode == RagQueryMode.RAG
    assert service.health()["status"] == "disabled"


def test_router_distinguishes_live_and_history():
    router = RagQueryRouter()
    assert router.classify("Olá") == RagQueryMode.NO_RAG
    assert router.classify("Como está a fila agora?") == RagQueryMode.LIVE
    assert router.classify("Como resolvemos isso anteriormente?") == RagQueryMode.RAG
    assert router.classify("Por que a fila está travada novamente?") == RagQueryMode.RAG_LIVE


def test_chunker_has_overlap_without_duplicate_tail():
    chunker = RagChunker(chunk_size=4, overlap=1)
    chunks = chunker.split("a b c d e f g")
    assert [chunk.content for chunk in chunks] == ["a b c d", "d e f g"]


def test_sanitizer_redacts_common_secrets():
    sanitizer = RagSanitizer()
    sanitized = sanitizer.sanitize("api_key=abc123 password:secret")
    assert "abc123" not in sanitized
    assert "password:secret" not in sanitized
    assert sanitized.count("[REDACTED]") == 2


def test_super_admin_applies_safe_limits():
    rag = RagService(settings=RagSettings(enabled=True))
    admin = RagAdminService(rag)
    updated = admin.update_settings({"top_k": 3, "cache_ttl_seconds": 300})
    assert updated["top_k"] == 3
    assert updated["cache_ttl_seconds"] == 300


def test_super_admin_rejects_unsafe_worker_concurrency():
    rag = RagService()
    admin = RagAdminService(rag)
    try:
        admin.update_settings({"index_worker_concurrency": 99})
    except ValueError as exc:
        assert "between 1 and 4" in str(exc)
    else:
        raise AssertionError("unsafe concurrency should fail")
