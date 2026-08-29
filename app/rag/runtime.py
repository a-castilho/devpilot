from __future__ import annotations

from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.db import SessionLocal
from app.models import ProviderCredential, Workspace
from app.services.vault import Vault

from .cache import RedisRagCache
from .db import get_rag_engine
from .embedding import EmbeddingProvider, LocalHashEmbeddingProvider, OpenAIEmbeddingProvider
from .service import NullRagCache, NullRagRepository, RagService, RagSettings
from .settings_store import load_runtime_settings
from .vector_repository import PgVectorRagRepository


def _stored_openai_api_key() -> str:
    """Resolve the enabled OpenAI credential from the default workspace vault."""
    try:
        with SessionLocal() as db:
            workspace_id = db.scalar(select(Workspace.id).where(Workspace.slug == "default"))
            if not workspace_id:
                return ""
            item = db.scalar(
                select(ProviderCredential)
                .where(
                    ProviderCredential.workspace_id == workspace_id,
                    ProviderCredential.provider == "openai",
                    ProviderCredential.enabled.is_(True),
                )
                .order_by(ProviderCredential.created_at.desc())
                .limit(1)
            )
            if not item:
                return ""
            return Vault().decrypt(item.encrypted_secret).strip()
    except (RuntimeError, ValueError, SQLAlchemyError):
        return ""


def _embedding_api_key() -> str:
    return _stored_openai_api_key()


def embedding_key_configured() -> bool:
    return bool(_embedding_api_key())


def _embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    api_key = _embedding_api_key()
    if api_key:
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=settings.rag_embedding_model,
            base_url=settings.rag_embedding_base_url,
            dimensions=settings.rag_embedding_dimensions,
        )
    return LocalHashEmbeddingProvider(dimensions=settings.rag_embedding_dimensions)


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
    # Runtime settings belong to the same storage used by documents, chunks and
    # index jobs. This keeps RAG configuration persistent even when the DevPilot
    # core database is SQLite and RAG uses PostgreSQL/pgvector separately.
    values.update({key: value for key, value in load_runtime_settings(get_rag_engine()).items() if key in values})
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
    if rag_engine.dialect.name == "postgresql":
        repository = PgVectorRagRepository(rag_engine, _embedding_provider())

    return RagService(settings=rag_settings, repository=repository, cache=cache)


def reload_rag_service() -> RagService:
    get_rag_service.cache_clear()
    return get_rag_service()


def get_rag_embedder() -> EmbeddingProvider | None:
    rag_engine = get_rag_engine()
    if rag_engine.dialect.name != "postgresql":
        return None
    return _embedding_provider()
