import time

from app.db import SessionLocal
from app.rag.worker import process_one_rag_job
from app.services.delivery_recovery_worker import process_one_pending_delivery
from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.worker import process_one


def main() -> None:
    try:
        runtime = worker_runtime_paths()
    except WorkerRuntimeError as error:
        print(f"[worker] PRECHECK FAILED: {error}", flush=True)
        raise SystemExit(78) from error

    print(
        "[worker] runtime OK: "
        + ", ".join(f"{tool}={path}" for tool, path in runtime.items()),
        flush=True,
    )

    while True:
        rag_processed = False
        delivery_processed = False
        with SessionLocal() as db:
            rag_processed = process_one_rag_job(db)
        with SessionLocal() as db:
            delivery_processed = process_one_pending_delivery(db)

        task_processed = process_one()
        if not rag_processed and not delivery_processed and not task_processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
