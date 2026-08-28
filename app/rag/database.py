from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import get_settings


def _rag_database_url() -> str:
    settings = get_settings()
    explicit = settings.rag_database_url.strip()
    if explicit:
        return explicit
    if settings.database_url.startswith("postgresql"):
        return settings.database_url
    return ""


def create_rag_engine() -> Engine | None:
    url = _rag_database_url()
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


rag_engine = create_rag_engine()
