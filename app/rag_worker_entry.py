from __future__ import annotations

import time

from app.db import SessionLocal
from app.rag.database import rag_engine
from app.rag.schema import ensure_rag_schema
from app.rag.worker import process_one_rag_job


def main() -> None:
    if rag_engine is None or rag_engine.dialect.name != "postgresql":
        raise SystemExit("RAG database is not configured")
    if not ensure_rag_schema(rag_engine):
        raise SystemExit("RAG PostgreSQL/pgvector schema is unavailable")

    print("[rag-worker] runtime OK", flush=True)
    while True:
        with SessionLocal() as db:
            processed = process_one_rag_job(db)
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
