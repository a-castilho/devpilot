from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TextChunk:
    index: int
    content: str


class RagChunker:
    """Low-memory text chunker with configurable overlap.

    Token counts are approximated by whitespace-separated words at this layer so
    chunking stays provider-agnostic. A provider-specific tokenizer may replace
    this implementation later without changing callers.
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, content: str) -> list[TextChunk]:
        words = content.split()
        if not words:
            return []
        step = self.chunk_size - self.overlap
        chunks: list[TextChunk] = []
        for start in range(0, len(words), step):
            piece = words[start : start + self.chunk_size]
            if not piece:
                break
            chunks.append(TextChunk(index=len(chunks), content=" ".join(piece)))
            if start + self.chunk_size >= len(words):
                break
        return chunks
