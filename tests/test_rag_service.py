from app.rag.admin import RagAdminService
from app.rag.chunking import RagChunker
from app.rag.sanitizer import RagSanitizer
from app.rag.service import RagQueryMode, RagQueryRouter, RagService, RagSettings, RetrievalChunk, RetrievalResult


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
    assert router.classify("oito commits anteriores") == RagQueryMode.RAG


def test_chunker_has_overlap_without_duplicate_tail():
    chunker = RagChunker(chunk_size=4, overlap=1)
    chunks = chunker.split("a b c d e f g")
    assert [chunk.content for chunk in chunks] == ["a b c d", "d e f g"]


def test_sanitizer_redacts_common_and_quoted_secrets():
    sanitizer = RagSanitizer()
    content = "api_key=abc123 password:secret token=\"quoted-token\" 'secret': 'quoted-secret'"
    sanitized = sanitizer.sanitize(content)
    for secret in ("abc123", "password:secret", "quoted-token", "quoted-secret"):
        assert secret not in sanitized
    assert sanitized.count("[REDACTED]") == 4


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


def test_super_admin_rejects_non_finite_similarity_threshold():
    admin = RagAdminService(RagService())
    for invalid in (float("nan"), float("inf"), True, "0.7"):
        try:
            admin.update_settings({"similarity_threshold": invalid})
        except ValueError as exc:
            assert "finite number" in str(exc)
        else:
            raise AssertionError(f"invalid threshold should fail: {invalid!r}")


def test_cache_key_changes_with_retrieval_settings():
    class Cache:
        def __init__(self):
            self.values = {}

        def get(self, key):
            return self.values.get(key)

        def set(self, key, value, ttl_seconds):
            self.values[key] = value

        def invalidate_project(self, organization_id, project_id):
            return None

        def health(self):
            return {"status": "healthy"}

    class Repository:
        def __init__(self):
            self.calls = 0

        def retrieve(self, **kwargs):
            self.calls += 1
            return [RetrievalChunk(str(self.calls), "documentation", None, "README.md", "contexto", 0.91, {})]

        def record_query(self, **kwargs):
            return None

        def health(self):
            return {"status": "healthy"}

    cache = Cache()
    repository = Repository()
    service = RagService(settings=RagSettings(enabled=True, top_k=5), repository=repository, cache=cache)
    service.retrieve(organization_id="org-1", project_id="project-1", query="arquitetura")
    service.settings.top_k = 3
    service.retrieve(organization_id="org-1", project_id="project-1", query="arquitetura")
    assert repository.calls == 2


def test_retrieval_records_privacy_safe_telemetry():
    class Repository:
        def __init__(self):
            self.events = []

        def retrieve(self, **kwargs):
            return [RetrievalChunk("c1", "documentation", "README.md", "README.md", "contexto", 0.91, {})]

        def record_query(self, **kwargs):
            self.events.append(kwargs)

        def health(self):
            return {"status": "healthy"}

    repository = Repository()
    service = RagService(settings=RagSettings(enabled=True, cache_enabled=False), repository=repository)
    result = service.retrieve(organization_id="org-1", project_id="project-1", query="arquitetura do sistema")
    assert len(result.chunks) == 1
    assert len(repository.events) == 1
    event = repository.events[0]
    assert event["query_type"] == "RAG"
    assert event["cache_hit"] is False
    assert event["retrieved_chunks"] == 1
    assert "query" in event


def test_telemetry_failure_does_not_break_retrieval():
    class Repository:
        def retrieve(self, **kwargs):
            return [RetrievalChunk("c1", "documentation", None, "README.md", "contexto", 0.91, {})]

        def record_query(self, **kwargs):
            raise RuntimeError("telemetry unavailable")

        def health(self):
            return {"status": "healthy"}

    service = RagService(settings=RagSettings(enabled=True, cache_enabled=False), repository=Repository())
    result = service.retrieve(organization_id="org-1", project_id="project-1", query="arquitetura")
    assert len(result.chunks) == 1
