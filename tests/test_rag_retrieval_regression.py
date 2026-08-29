from __future__ import annotations

from types import SimpleNamespace

from app.rag.embedding import LocalHashEmbeddingProvider, OpenAIEmbeddingProvider, embedding_info
from app.rag.service import NullRagCache, RagService, RagSettings, RetrievalChunk
from app.rag.vector_repository import LOCAL_HASH_SIMILARITY_CAP, PgVectorRagRepository


def test_local_hash_threshold_is_calibrated_for_lexical_retrieval():
    repository = PgVectorRagRepository(SimpleNamespace(), LocalHashEmbeddingProvider(dimensions=1536))

    assert repository.effective_threshold(0.70) == LOCAL_HASH_SIMILARITY_CAP
    assert repository.effective_threshold(0.05) == 0.05


def test_openai_threshold_keeps_admin_configuration():
    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small", dimensions=1536)
    repository = PgVectorRagRepository(SimpleNamespace(), provider)

    assert repository.effective_threshold(0.70) == 0.70


def test_local_hash_can_match_the_a_castilho_readme_with_effective_threshold():
    provider = LocalHashEmbeddingProvider(dimensions=1536)
    query = provider.embed("o que faz o projeto a-castilho")
    readme = provider.embed(
        """# ACS — Site Institucional
        Site institucional da ACS, desenvolvido em Next.js com foco em posicionamento comercial como parceira de software, produto e inteligência artificial.
        Stack Next.js 15 React 19 Neon Postgres Vercel.
        Principais recursos: Home responsiva, soluções, processo, impacto, FAQ, formulário de leads, API contact e deploy Vercel.
        COMPROMISSO-GERAL-A-CASTILHO."""
    )
    similarity = sum(left * right for left, right in zip(query, readme, strict=True))

    assert similarity > 0.05
    assert similarity < 0.70


def test_embedding_identity_is_stable_and_does_not_expose_secret():
    provider = OpenAIEmbeddingProvider(api_key="very-secret-key", model="text-embedding-3-small", dimensions=1536)
    first = embedding_info(provider)
    second = embedding_info(provider)

    assert first == second
    assert first["provider"] == "openai"
    assert first["model"] == "text-embedding-3-small"
    assert first["dimensions"] == 1536
    assert first["signature"]
    assert "very-secret-key" not in str(first)


def test_service_returns_candidates_when_nothing_passes_threshold():
    candidate = RetrievalChunk("c1", "documentation", "README.md", "README.md", "site institucional", 0.09, {})

    class Repository:
        def effective_threshold(self, configured_threshold):
            return 0.12

        def embedding_info(self):
            return {"provider": "local_hash", "model": "feature-hash-v1", "signature": "sig-local"}

        def retrieve(self, **kwargs):
            assert kwargs["similarity_threshold"] == 0.12
            return []

        def retrieve_candidates(self, **kwargs):
            return [candidate]

        def index_state(self, **kwargs):
            return {"reindex_required": False, "legacy_vectors": 1}

        def record_query(self, **kwargs):
            return None

        def health(self):
            return {"status": "healthy", "backend": "fake"}

    service = RagService(
        settings=RagSettings(enabled=True, cache_enabled=False, similarity_threshold=0.70),
        repository=Repository(),
    )
    result = service.retrieve(
        organization_id="org-1",
        project_id="project-1",
        query="o que faz o projeto",
        diagnostic=True,
    )

    assert result.chunks == []
    assert result.candidates == [candidate]
    assert result.configured_threshold == 0.70
    assert result.effective_threshold == 0.12
    assert result.embedding["provider"] == "local_hash"
    assert result.index_state["legacy_vectors"] == 1


def test_disabled_optional_cache_does_not_degrade_healthy_rag():
    class Repository:
        def retrieve(self, **kwargs):
            return []

        def record_query(self, **kwargs):
            return None

        def health(self):
            return {"status": "healthy", "backend": "fake"}

    service = RagService(
        settings=RagSettings(enabled=True, cache_enabled=True),
        repository=Repository(),
        cache=NullRagCache(),
    )

    assert service.health()["status"] == "healthy"
    assert service.health()["cache"]["status"] == "disabled"


def test_cache_outage_is_fail_open_for_retrieval_and_invalidation():
    chunk = RetrievalChunk("c1", "documentation", "README.md", "README.md", "contexto", 0.91, {})

    class Repository:
        def retrieve(self, **kwargs):
            return [chunk]

        def record_query(self, **kwargs):
            return None

        def health(self):
            return {"status": "healthy", "backend": "fake"}

    class BrokenCache:
        def get(self, key):
            raise ConnectionError("redis down")

        def set(self, key, value, ttl_seconds):
            raise ConnectionError("redis down")

        def invalidate_project(self, organization_id, project_id):
            raise ConnectionError("redis down")

        def health(self):
            return {"status": "degraded", "backend": "redis"}

    service = RagService(
        settings=RagSettings(enabled=True, cache_enabled=True),
        repository=Repository(),
        cache=BrokenCache(),
    )
    result = service.retrieve(organization_id="org", project_id="project", query="arquitetura")

    assert result.chunks == [chunk]
    assert result.cache_hit is False
    service.invalidate_project(organization_id="org", project_id="project")
    assert service.health()["status"] == "degraded"


def test_cache_key_changes_when_embedding_provider_changes():
    class Repository:
        signature = "provider-a"

        def retrieve(self, **kwargs):
            return []

        def record_query(self, **kwargs):
            return None

        def health(self):
            return {"status": "healthy"}

        def embedding_info(self):
            return {"provider": "fake", "model": "model", "signature": self.signature}

    repository = Repository()
    service = RagService(settings=RagSettings(enabled=True), repository=repository)
    first = service._cache_key("org", "project", "query")
    repository.signature = "provider-b"
    second = service._cache_key("org", "project", "query")

    assert first != second
