from __future__ import annotations

import threading

from app.db import SessionLocal
from app.services.delivery_recovery_worker import process_one_pending_delivery
from app.services.runtime_preflight import worker_runtime_paths
from app.worker import process_one


class EmbeddedWorker:
    """Small in-process worker for single-instance homologation environments.

    Production deployments should keep using a dedicated worker service. This
    helper exists so a free Render web service can exercise the complete queue
    and final-delivery recovery flow without provisioning a paid background worker.
    """

    def __init__(self, poll_seconds: float = 2.0) -> None:
        self.poll_seconds = max(0.05, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return

        runtime = worker_runtime_paths()
        print(
            "[embedded-worker] runtime OK: "
            + ", ".join(f"{tool}={path}" for tool, path in runtime.items()),
            flush=True,
        )

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="devpilot-embedded-worker",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            task_processed = False
            delivery_processed = False

            try:
                task_processed = process_one()
            except Exception as error:  # pragma: no cover - defensive runtime guard
                print(f"[embedded-worker] task loop error: {error}", flush=True)

            try:
                with SessionLocal() as db:
                    delivery_processed = process_one_pending_delivery(db)
            except Exception as error:  # pragma: no cover - defensive runtime guard
                print(f"[embedded-worker] delivery loop error: {error}", flush=True)

            if not task_processed and not delivery_processed:
                self._stop.wait(self.poll_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))
