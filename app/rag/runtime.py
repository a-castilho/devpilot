from __future__ import annotations

import os
from functools import lru_cache

from app.config import get_settings
from app.db import engine as core_engine

from .cache import RedisRagCache
from .db import get_rag_engine
from .embedding import OpenAIEmbeddingProvider
from .service import NullRagCache, NullRagRepository, RagService, RagSettings
from .settings_store import load_runtime_settings
from .vector_repository import PgVectorRagRepository


def _embedding_api_key() -> str:
    settings = get_settings()
    return settings.rag_embedding_api_key.strip() or os.getenv("OPENAI_API_KEY", "").strip()


def _rag_settings() -> RagSettings:
    settings = get_settings()
    values = {
        "enabled": settings.rag_enabled,
        "cache_enabled": settings.rag_cache_enabled,
        "git_enabled": settings.rag_git_enabled,
        "docs_enabled": settings.rag_docs_enabled,
        "audit_enabled": settings.rag_audit_enabled,
        "tasks_enabled": settings.rag_tasks_enabled,
        "logs_enabled": settings.rag_logs_enabled,
        "top_k": settings.rag_top_k,
        "similarity_threshold": settings.rag_similarity_threshold,
        "cache_ttl_seconds": settings.rag_cache_ttl_seconds,
        "chunk_size_tokens": settings.rag_chunk_size_tokens,
        "chunk_overlap_tokens": settings.rag_chunk_overlap_tokens,
        "index_batch_size": settings.rag_index_batch_size,
        "index_worker_concurrency": settings.rag_index_worker_concurrency,
    }
    values.update({key: value for key, value in load_runtime_settings(core_engine).items() if key in values})
    return RagSettings(**values)


@lru_cache
def get_rag_service() -> RagService:
    settings = get_settings()
    rag_settings = _rag_settings()

    cache = NullRagCache()
    if rag_settings.cache_enabled and settings.redis_url:
        try:
            cache = RedisRagCache(settings.redis_url)
        except RuntimeError:
            cache = NullRagCache()

    repository = NullRagRepository()
    rag_engine = get_rag_engine()
    api_key = _embedding_api_key()
    if rag_engine.dialect.name == "postgresql" and api_key:
        embedder = OpenAIEmbeddingProvider(
            api_key=api_key,
            model=settings.rag_embedding_model,
            base_url=settings.rag_embedding_base_url,
            dimensions=settings.rag_embedding_dimensions,
        )
        repository = PgVectorRagRepository(rag_engine, embedder)

    return RagService(settings=rag_settings, repository=repository, cache=cache)


def reload_rag_service() -> RagService:
    get_rag_service.cache_clear()
    return get_rag_service()


def get_rag_embedder() -> OpenAIEmbeddingProvider | None:
    settings = get_settings()
    rag_engine = get_rag_engine()
    api_key = _embedding_api_key()
    if rag_engine.dialect.name != "postgresql" or not api_key:
        return None
    return OpenAIEmbeddingProvider(
        api_key=api_key,
        model=settings.rag_embedding_model,
        base_url=settings.rag_embedding_base_url,
        dimensions=settings.rag_embedding_dimensions,
    )
