from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Protocol

import httpx


class EmbeddingProvider(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...
    def info(self) -> dict[str, Any]: ...


def embedding_info(provider: EmbeddingProvider) -> dict[str, Any]:
    resolver = getattr(provider, "info", None)
    if callable(resolver):
        data = dict(resolver())
    else:
        data = {
            "provider": provider.__class__.__name__.lower(),
            "model": provider.__class__.__name__,
            "dimensions": int(provider.dimensions),
            "semantic": None,
        }
    data.setdefault("dimensions", int(provider.dimensions))
    data["signature"] = embedding_signature(provider, info=data)
    return data


def embedding_signature(provider: EmbeddingProvider, *, info: dict[str, Any] | None = None) -> str:
    data = info or {
        "provider": provider.__class__.__name__.lower(),
        "model": provider.__class__.__name__,
        "dimensions": int(provider.dimensions),
    }
    raw = f"{data.get('provider', '')}:{data.get('model', '')}:{int(data.get('dimensions') or provider.dimensions)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class LocalHashEmbeddingProvider:
    """Deterministic CPU-only embedding fallback with no external model or API key.

    This uses feature hashing over normalized word tokens and character trigrams.
    It is intentionally lightweight for constrained local hosts. It is not a neural
    semantic embedding model, but it preserves useful lexical similarity and keeps
    the RAG pipeline operational offline.
    """

    _token_re = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
    model = "feature-hash-v1"

    def __init__(self, *, dimensions: int = 1536) -> None:
        dimensions = int(dimensions)
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")
        self.dimensions = dimensions

    def info(self) -> dict[str, Any]:
        return {
            "provider": "local_hash",
            "model": self.model,
            "dimensions": self.dimensions,
            "semantic": False,
            "offline": True,
        }

    @staticmethod
    def _feature_hash(feature: str) -> tuple[int, float]:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big", signed=False)
        sign = -1.0 if value & 1 else 1.0
        return value, sign

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = " ".join(self._token_re.findall(str(text).casefold()))
        if not normalized:
            return vector

        words = normalized.split()
        features: list[tuple[str, float]] = [(f"w:{word}", 1.0) for word in words]
        compact = normalized.replace(" ", "_")
        features.extend(
            (f"c3:{compact[index:index + 3]}", 0.35)
            for index in range(max(0, len(compact) - 2))
        )

        for feature, weight in features:
            value, sign = self._feature_hash(feature)
            vector[value % self.dimensions] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


class OpenAIEmbeddingProvider:
    """Small synchronous embedding adapter using an OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimensions: int = 1536,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Embedding API key is required")
        self.api_key = api_key.strip()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.dimensions = int(dimensions)
        self.timeout_seconds = float(timeout_seconds)

    def info(self) -> dict[str, Any]:
        return {
            "provider": "openai",
            "model": self.model,
            "dimensions": self.dimensions,
            "semantic": True,
            "offline": False,
        }

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": text, "dimensions": self.dimensions}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        values = data["data"][0]["embedding"]
        if len(values) != self.dimensions:
            raise RuntimeError("Embedding dimension mismatch")
        return [float(value) for value in values]
