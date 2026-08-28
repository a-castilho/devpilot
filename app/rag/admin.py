from __future__ import annotations

from dataclasses import replace
from typing import Any

from .service import RagService, RagSettings


class RagAdminService:
    """Administrative facade used by Super Admin API/UI.

    Persistence/audit hooks can be injected later; this class intentionally keeps
    the UI decoupled from Redis, pgvector and embedding providers.
    """

    _SAFE_INT_FIELDS = {
        "top_k": (1, 10),
        "cache_ttl_seconds": (60, 86400),
        "chunk_size_tokens": (100, 2000),
        "chunk_overlap_tokens": (0, 300),
        "index_batch_size": (1, 100),
        "index_worker_concurrency": (1, 4),
    }
    _BOOL_FIELDS = {
        "enabled",
        "cache_enabled",
        "git_enabled",
        "docs_enabled",
        "audit_enabled",
        "tasks_enabled",
        "logs_enabled",
    }

    def __init__(self, rag: RagService) -> None:
        self.rag = rag

    def overview(self) -> dict[str, Any]:
        return self.rag.overview()

    def health(self) -> dict[str, Any]:
        return self.rag.health()

    def settings(self) -> dict[str, Any]:
        return self.rag.settings.public_dict()

    def update_settings(self, changes: dict[str, Any]) -> dict[str, Any]:
        current = self.rag.settings
        valid: dict[str, Any] = {}
        for key, value in changes.items():
            if key in self._BOOL_FIELDS:
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be boolean")
                valid[key] = value
            elif key in self._SAFE_INT_FIELDS:
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"{key} must be integer")
                minimum, maximum = self._SAFE_INT_FIELDS[key]
                if value < minimum or value > maximum:
                    raise ValueError(f"{key} must be between {minimum} and {maximum}")
                valid[key] = value
            elif key == "similarity_threshold":
                numeric = float(value)
                if numeric < 0.0 or numeric > 1.0:
                    raise ValueError("similarity_threshold must be between 0 and 1")
                valid[key] = numeric
            else:
                raise ValueError(f"unsupported RAG setting: {key}")

        overlap = valid.get("chunk_overlap_tokens", current.chunk_overlap_tokens)
        size = valid.get("chunk_size_tokens", current.chunk_size_tokens)
        if overlap >= size:
            raise ValueError("chunk_overlap_tokens must be smaller than chunk_size_tokens")

        updated: RagSettings = replace(current, **valid)
        self.rag.settings = updated
        return updated.public_dict()
