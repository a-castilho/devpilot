import time

from app.db import SessionLocal
from app.rag.worker import process_one_rag_job
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.worker import process_one


def main() -> None:
    try:
        runtime = worker_runtime_paths()
    except WorkerRuntimeError as error:
        print(f"[worker] PRECHECK FAILED: {error}", flush=True)
        raise SystemExit(78) from error

    from app import codex_runtime_auth as _codex_runtime_auth  # noqa: F401

    print(
        "[worker] runtime OK: "
        + ", ".join(f"{tool}={path}" for tool, path in runtime.items()),
        flush=True,
    )

    while True:
        rag_processed = False
        with SessionLocal() as db:
            rag_processed = process_one_rag_job(db)
        task_processed = process_one()
        if not rag_processed and not task_processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
