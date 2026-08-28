from __future__ import annotations

import time

from app.db import SessionLocal
from app.rag.worker import process_one_rag_job


def main() -> None:
    print("[rag-worker] iniciado", flush=True)
    while True:
        processed = False
        with SessionLocal() as db:
            processed = process_one_rag_job(db)
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
