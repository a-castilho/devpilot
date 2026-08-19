from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agentos.embeddings import EmbeddingClient
from app.agentos.models import KnowledgeChunk


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    if len(clean) <= max_chars:
        return [clean]

    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + max_chars)
        if end < len(clean):
            boundary = clean.rfind(" ", start + max_chars // 2, end)
            if boundary > start:
                end = boundary
        chunk = clean[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return -1.0
    return dot / (left_norm * right_norm)


def ingest(
    db: Session,
    *,
    workspace_id: str,
    project_id: str | None,
    namespace: str,
    source: str,
    content: str,
    metadata: dict[str, Any],
) -> list[KnowledgeChunk]:
    embedder = EmbeddingClient()
    created: list[KnowledgeChunk] = []
    for position, chunk in enumerate(chunk_text(content)):
        result = embedder.embed(chunk)
        item = KnowledgeChunk(
            workspace_id=workspace_id,
            project_id=project_id,
            namespace=namespace,
            source=source,
            position=position,
            content=chunk,
            embedding=json.dumps(result.vector),
            embedding_model=result.model,
            embedding_provider=result.provider,
            metadata_json=json.dumps(metadata),
        )
        db.add(item)
        created.append(item)
    db.flush()
    return created


def search(
    db: Session,
    *,
    workspace_id: str,
    project_id: str | None,
    namespace: str,
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    query_embedding = EmbeddingClient().embed(query).vector
    statement = select(KnowledgeChunk).where(
        KnowledgeChunk.workspace_id == workspace_id,
        KnowledgeChunk.namespace == namespace,
    )
    if project_id is not None:
        statement = statement.where(KnowledgeChunk.project_id == project_id)

    scored: list[tuple[float, KnowledgeChunk]] = []
    for item in db.scalars(statement).all():
        try:
            stored = [float(value) for value in json.loads(item.embedding)]
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        score = cosine_similarity(query_embedding, stored)
        if score >= 0:
            scored.append((score, item))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {
            "id": item.id,
            "score": round(score, 6),
            "source": item.source,
            "position": item.position,
            "content": item.content,
            "metadata": json.loads(item.metadata_json or "{}"),
            "embedding_model": item.embedding_model,
            "embedding_provider": item.embedding_provider,
        }
        for score, item in scored[:top_k]
    ]
