from __future__ import annotations

from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...


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
