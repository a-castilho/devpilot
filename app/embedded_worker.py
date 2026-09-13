from __future__ import annotations

import threading

from app.services.runtime_preflight import worker_runtime_paths
from app.services.stale_delivery_claims import recover_stale_delivery_claims
from app.worker import process_one


class EmbeddedWorker:
    """Small in-process worker for single-instance homologation environments.

    Production deployments should keep using a dedicated worker service. This
    helper exists so a free Render web service can exercise the complete queue
    flow without provisioning a paid background worker.
    """

    def __init__(self, poll_seconds: float = 2.0) -> None:
        self.poll_seconds = max(0.05, float(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_stale_recovery_at = 0.0

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

        # Recover final-delivery work abandoned by the previous Render instance
        # before claiming new queue items. This keeps homologation autonomous across
        # rolling deploys without changing the lease policy for unrelated tasks.
        recovered = recover_stale_delivery_claims()
        if recovered:
            print(f"[embedded-worker] recovered stale delivery tasks={recovered}", flush=True)

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="devpilot-embedded-worker",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                processed = process_one()
            except Exception as error:  # pragma: no cover - defensive runtime guard
                print(f"[embedded-worker] task loop error: {error}", flush=True)
                processed = False

            if not processed:
                self._stop.wait(self.poll_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=max(0.0, timeout))
