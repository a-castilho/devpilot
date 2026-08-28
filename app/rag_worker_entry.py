from __future__ import annotations

import time

from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionLocal
from app.rag.worker import process_one_rag_job


RETRY_DELAY_SECONDS = 2


def main() -> None:
    print("[rag-worker] iniciado", flush=True)
    while True:
        processed = False
        try:
            with SessionLocal() as db:
                processed = process_one_rag_job(db)
        except (SQLAlchemyError, OSError, RuntimeError) as exc:
            print(
                f"[rag-worker] falha transitória ({type(exc).__name__}); tentando novamente",
                flush=True,
            )
            time.sleep(RETRY_DELAY_SECONDS)
            continue
        if not processed:
            time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    main()
