from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    provider: str


def hashing_embedding(text: str, dimensions: int = 256) -> list[float]:
    """Very small deterministic fallback used only when the model service is unavailable."""
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = -1.0 if digest[4] & 1 else 1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class EmbeddingClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def embed(self, text: str) -> EmbeddingResult:
        if self.settings.ollama_embeddings_enabled:
            try:
                response = httpx.post(
                    f"{self.settings.ollama_base_url.rstrip('/')}/api/embed",
                    json={"model": self.settings.ollama_embedding_model, "input": text},
                    timeout=self.settings.model_timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                vector = payload["embeddings"][0]
                return EmbeddingResult(
                    vector=[float(value) for value in vector],
                    model=payload.get("model", self.settings.ollama_embedding_model),
                    provider="ollama",
                )
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
                if not self.settings.embedding_fallback_enabled:
                    raise

        return EmbeddingResult(
            vector=hashing_embedding(text),
            model="hashing-256",
            provider="local-fallback",
        )
