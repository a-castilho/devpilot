from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.db import engine

from .cache import RedisRagCache
from .embedding import OpenAIEmbeddingProvider
from .service import NullRagCache, NullRagRepository, RagService, RagSettings
from .vector_repository import PgVectorRagRepository


@lru_cache
def get_rag_service() -> RagService:
    settings = get_settings()
    rag_settings = RagSettings(
        enabled=settings.rag_enabled,
        cache_enabled=settings.rag_cache_enabled,
        git_enabled=settings.rag_git_enabled,
        docs_enabled=settings.rag_docs_enabled,
        audit_enabled=settings.rag_audit_enabled,
        tasks_enabled=settings.rag_tasks_enabled,
        logs_enabled=settings.rag_logs_enabled,
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        cache_ttl_seconds=settings.rag_cache_ttl_seconds,
        chunk_size_tokens=settings.rag_chunk_size_tokens,
        chunk_overlap_tokens=settings.rag_chunk_overlap_tokens,
        index_batch_size=settings.rag_index_batch_size,
        index_worker_concurrency=settings.rag_index_worker_concurrency,
    )

    cache = NullRagCache()
    if rag_settings.cache_enabled and settings.redis_url:
        try:
            cache = RedisRagCache(settings.redis_url)
        except RuntimeError:
            cache = NullRagCache()

    repository = NullRagRepository()
    if (
        engine.dialect.name == "postgresql"
        and settings.rag_embedding_api_key.strip()
    ):
        embedder = OpenAIEmbeddingProvider(
            api_key=settings.rag_embedding_api_key,
            model=settings.rag_embedding_model,
            base_url=settings.rag_embedding_base_url,
            dimensions=settings.rag_embedding_dimensions,
        )
        repository = PgVectorRagRepository(engine, embedder)

    return RagService(settings=rag_settings, repository=repository, cache=cache)


def get_rag_embedder() -> OpenAIEmbeddingProvider | None:
    settings = get_settings()
    if engine.dialect.name != "postgresql" or not settings.rag_embedding_api_key.strip():
        return None
    return OpenAIEmbeddingProvider(
        api_key=settings.rag_embedding_api_key,
        model=settings.rag_embedding_model,
        base_url=settings.rag_embedding_base_url,
        dimensions=settings.rag_embedding_dimensions,
    )
