from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import get_settings

from .schema import ensure_rag_schema


@lru_cache
def get_rag_engine() -> Engine:
    settings = get_settings()
    database_url = settings.rag_database_url.strip() or settings.database_url
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    ensure_rag_schema(engine, embedding_dimensions=settings.rag_embedding_dimensions)
    return engine
