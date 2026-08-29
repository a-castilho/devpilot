from __future__ import annotations

import hashlib
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol


class RagQueryMode(str, Enum):
    NO_RAG = "NO_RAG"
    RAG = "RAG"
    LIVE = "LIVE"
    RAG_LIVE = "RAG_LIVE"


@dataclass(slots=True)
class RagSettings:
    enabled: bool = False
    cache_enabled: bool = True
    git_enabled: bool = True
    docs_enabled: bool = True
    audit_enabled: bool = False
    tasks_enabled: bool = False
    logs_enabled: bool = False
    top_k: int = 5
    similarity_threshold: float = 0.70
    cache_ttl_seconds: int = 900
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 50
    index_batch_size: int = 10
    index_worker_concurrency: int = 1

    def public_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievalChunk:
    id: str
    source_type: str
    source_id: str | None
    source_path: str | None
    content: str
    score: float
    metadata: dict[str, Any]


@dataclass(slots=True)
class RetrievalResult:
    mode: RagQueryMode
    chunks: list[RetrievalChunk]
    cache_hit: bool = False
    retrieval_time_ms: float = 0.0
    configured_threshold: float = 0.0
    effective_threshold: float = 0.0
    embedding: dict[str, Any] = field(default_factory=dict)
    candidates: list[RetrievalChunk] = field(default_factory=list)
    index_state: dict[str, Any] = field(default_factory=dict)


class RagRepository(Protocol):
    def retrieve(self, *, organization_id: str, project_id: str, query: str, top_k: int, similarity_threshold: float) -> list[RetrievalChunk]: ...
    def record_query(self, *, organization_id: str, project_id: str, query: str, query_type: str, cache_hit: bool, retrieved_chunks: int, retrieval_time_ms: float) -> None: ...
    def health(self) -> dict[str, Any]: ...


class RagCache(Protocol):
    def get(self, key: str) -> RetrievalResult | None: ...
    def set(self, key: str, value: RetrievalResult, ttl_seconds: int) -> None: ...
    def invalidate_project(self, organization_id: str, project_id: str) -> None: ...
    def health(self) -> dict[str, Any]: ...


class NullRagRepository:
    def retrieve(self, **_: Any) -> list[RetrievalChunk]:
        return []

    def record_query(self, **_: Any) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {"status": "disabled", "backend": "null"}


class NullRagCache:
    def get(self, key: str) -> RetrievalResult | None:
        return None

    def set(self, key: str, value: RetrievalResult, ttl_seconds: int) -> None:
        return None

    def invalidate_project(self, organization_id: str, project_id: str) -> None:
        return None

    def health(self) -> dict[str, Any]:
        return {"status": "disabled", "backend": "null", "optional": True}


class RagQueryRouter:
    _GREETING_RE = re.compile(r"^(?:olá|ola|oi|bom dia|boa tarde|boa noite)(?=$|[\s!,.?:;])")
    _LIVE_TERMS = ("agora", "atual", "status", "saúde", "health", "fila", "worker", "cpu", "ram", "memória", "deploy")
    _HISTORY_TERMS = ("antes", "anterior", "novamente", "histórico", "historico", "decidido", "resolvemos", "documentação", "documentacao", "arquitetura", "commit")

    def classify(self, query: str) -> RagQueryMode:
        normalized = " ".join(query.lower().split())
        if not normalized or self._GREETING_RE.match(normalized):
            return RagQueryMode.NO_RAG
        live = any(term in normalized for term in self._LIVE_TERMS)
        history = any(term in normalized for term in self._HISTORY_TERMS)
        if live and history:
            return RagQueryMode.RAG_LIVE
        if live:
            return RagQueryMode.LIVE
        return RagQueryMode.RAG


class RagService:
    def __init__(self, *, settings: RagSettings | None = None, repository: RagRepository | None = None, cache: RagCache | None = None, router: RagQueryRouter | None = None) -> None:
        self.settings = settings or RagSettings()
        self.repository = repository or NullRagRepository()
        self.cache = cache or NullRagCache()
        self.router = router or RagQueryRouter()

    def embedding_info(self) -> dict[str, Any]:
        resolver = getattr(self.repository, "embedding_info", None)
        if callable(resolver):
            try:
                return dict(resolver())
            except Exception:
                return {}
        health = self.repository.health()
        return dict(health.get("embedding") or {})

    def effective_threshold(self) -> float:
        configured = float(self.settings.similarity_threshold)
        resolver = getattr(self.repository, "effective_threshold", None)
        if callable(resolver):
            try:
                return float(resolver(configured))
            except Exception:
                return configured
        return configured

    def index_state(self, *, organization_id: str, project_id: str) -> dict[str, Any]:
        resolver = getattr(self.repository, "index_state", None)
        if not callable(resolver):
            return {}
        try:
            return dict(resolver(organization_id=organization_id, project_id=project_id))
        except Exception as error:
            return {"status": "error", "detail": str(error)[:300]}

    def retrieve(self, *, organization_id: str, project_id: str, query: str, diagnostic: bool = False) -> RetrievalResult:
        mode = self.router.classify(query)
        configured_threshold = float(self.settings.similarity_threshold)
        effective_threshold = self.effective_threshold()
        embedding = self.embedding_info()
        if not self.settings.enabled or mode in {RagQueryMode.NO_RAG, RagQueryMode.LIVE}:
            return RetrievalResult(
                mode=mode,
                chunks=[],
                configured_threshold=configured_threshold,
                effective_threshold=effective_threshold,
                embedding=embedding,
            )

        started = time.perf_counter()
        cache_key = self._cache_key(
            organization_id,
            project_id,
            query,
            effective_threshold=effective_threshold,
            embedding=embedding,
            diagnostic=diagnostic,
        )
        if self.settings.cache_enabled:
            cached = self.cache.get(cache_key)
            if cached is not None:
                cached.cache_hit = True
                cached.retrieval_time_ms = (time.perf_counter() - started) * 1000.0
                self._record_query_safely(
                    organization_id=organization_id,
                    project_id=project_id,
                    query=query,
                    query_type=mode.value,
                    cache_hit=True,
                    retrieved_chunks=len(cached.chunks),
                    retrieval_time_ms=cached.retrieval_time_ms,
                )
                return cached

        chunks = self.repository.retrieve(
            organization_id=organization_id,
            project_id=project_id,
            query=query,
            top_k=self.settings.top_k,
            similarity_threshold=effective_threshold,
        )
        candidates = list(chunks)
        if diagnostic and len(candidates) < self.settings.top_k:
            diagnostician = getattr(self.repository, "retrieve_candidates", None)
            if callable(diagnostician):
                try:
                    candidates = list(
                        diagnostician(
                            organization_id=organization_id,
                            project_id=project_id,
                            query=query,
                            top_k=self.settings.top_k,
                        )
                    )
                except Exception:
                    candidates = list(chunks)

        result = RetrievalResult(
            mode=mode,
            chunks=chunks,
            retrieval_time_ms=(time.perf_counter() - started) * 1000.0,
            configured_threshold=configured_threshold,
            effective_threshold=effective_threshold,
            embedding=embedding,
            candidates=candidates,
            index_state=self.index_state(organization_id=organization_id, project_id=project_id),
        )
        self._record_query_safely(
            organization_id=organization_id,
            project_id=project_id,
            query=query,
            query_type=mode.value,
            cache_hit=False,
            retrieved_chunks=len(chunks),
            retrieval_time_ms=result.retrieval_time_ms,
        )
        if self.settings.cache_enabled:
            self.cache.set(cache_key, result, self.settings.cache_ttl_seconds)
        return result

    def _record_query_safely(self, **event: Any) -> None:
        recorder = getattr(self.repository, "record_query", None)
        if not callable(recorder):
            return
        try:
            recorder(**event)
        except Exception:
            return

    def invalidate_project(self, *, organization_id: str, project_id: str) -> None:
        self.cache.invalidate_project(organization_id, project_id)

    def health(self) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"status": "disabled", "enabled": False}
        repository = self.repository.health()
        cache = self.cache.health() if self.settings.cache_enabled else {"status": "disabled", "optional": True}
        degraded = repository.get("status") not in {"healthy", "ok"}
        cache_status = str(cache.get("status") or "").lower()
        if self.settings.cache_enabled and cache_status in {"error", "degraded", "unhealthy"}:
            degraded = True
        return {
            "status": "degraded" if degraded else "healthy",
            "enabled": True,
            "repository": repository,
            "cache": cache,
            "embedding": self.embedding_info(),
            "retrieval": {
                "configured_threshold": float(self.settings.similarity_threshold),
                "effective_threshold": self.effective_threshold(),
                "top_k": int(self.settings.top_k),
            },
        }

    def overview(self) -> dict[str, Any]:
        return {"settings": self.settings.public_dict(), "health": self.health()}

    def _cache_key(
        self,
        organization_id: str,
        project_id: str,
        query: str,
        *,
        effective_threshold: float | None = None,
        embedding: dict[str, Any] | None = None,
        diagnostic: bool = False,
    ) -> str:
        normalized = " ".join(query.lower().split())
        threshold = self.effective_threshold() if effective_threshold is None else float(effective_threshold)
        provider = embedding if embedding is not None else self.embedding_info()
        signature = str(provider.get("signature") or provider.get("model") or provider.get("provider") or "unknown")
        retrieval_config = (
            f"top_k={self.settings.top_k};threshold={threshold:.12g};"
            f"embedding={signature};diagnostic={int(bool(diagnostic))}"
        )
        digest = hashlib.sha256(f"{retrieval_config}\n{normalized}".encode("utf-8")).hexdigest()
        return f"rag:retrieval:{organization_id}:{project_id}:{digest}"
