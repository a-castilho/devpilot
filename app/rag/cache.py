from __future__ import annotations

import json
from typing import Any

from .service import RagQueryMode, RetrievalChunk, RetrievalResult


class RedisRagCache:
    """Redis-backed cache restricted to the ``rag:`` namespace.

    Import is lazy so DEVpilot can still boot without the optional Redis dependency.
    """

    def __init__(self, redis_url: str) -> None:
        if not redis_url:
            raise ValueError("redis_url is required")
        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError("Redis support requires the optional 'rag' dependencies") from exc
        self.client = Redis.from_url(redis_url, decode_responses=True, socket_timeout=1.0)

    @staticmethod
    def _chunks(items: list[dict[str, Any]]) -> list[RetrievalChunk]:
        return [RetrievalChunk(**item) for item in items]

    def get(self, key: str) -> RetrievalResult | None:
        raw = self.client.get(key)
        if not raw:
            return None
        data = json.loads(raw)
        return RetrievalResult(
            mode=RagQueryMode(data["mode"]),
            chunks=self._chunks(data.get("chunks", [])),
            cache_hit=True,
            retrieval_time_ms=float(data.get("retrieval_time_ms", 0.0)),
            configured_threshold=float(data.get("configured_threshold", 0.0)),
            effective_threshold=float(data.get("effective_threshold", 0.0)),
            embedding=dict(data.get("embedding") or {}),
            candidates=self._chunks(data.get("candidates", [])),
            index_state=dict(data.get("index_state") or {}),
        )

    @staticmethod
    def _chunk_payload(chunk: RetrievalChunk) -> dict[str, Any]:
        return {
            "id": chunk.id,
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "source_path": chunk.source_path,
            "content": chunk.content,
            "score": chunk.score,
            "metadata": chunk.metadata,
        }

    def set(self, key: str, value: RetrievalResult, ttl_seconds: int) -> None:
        payload: dict[str, Any] = {
            "mode": value.mode.value,
            "chunks": [self._chunk_payload(chunk) for chunk in value.chunks],
            "retrieval_time_ms": value.retrieval_time_ms,
            "configured_threshold": value.configured_threshold,
            "effective_threshold": value.effective_threshold,
            "embedding": value.embedding,
            "candidates": [self._chunk_payload(chunk) for chunk in value.candidates],
            "index_state": value.index_state,
        }
        self.client.setex(key, ttl_seconds, json.dumps(payload, ensure_ascii=False))

    def invalidate_project(self, organization_id: str, project_id: str) -> None:
        pattern = f"rag:retrieval:{organization_id}:{project_id}:*"
        batch: list[str] = []
        for key in self.client.scan_iter(match=pattern, count=100):
            batch.append(key)
            if len(batch) >= 100:
                self.client.delete(*batch)
                batch.clear()
        if batch:
            self.client.delete(*batch)

    def health(self) -> dict[str, Any]:
        try:
            self.client.ping()
            info = self.client.info(section="memory")
            return {
                "status": "healthy",
                "backend": "redis",
                "used_memory": int(info.get("used_memory", 0)),
                "maxmemory": int(info.get("maxmemory", 0)),
            }
        except Exception as exc:  # Redis outage must degrade RAG, not DEVpilot.
            return {"status": "degraded", "backend": "redis", "error": type(exc).__name__}
