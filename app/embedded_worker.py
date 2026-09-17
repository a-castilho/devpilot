from __future__ import annotations

import os
import threading

from app.services.runtime_preflight import worker_runtime_paths
from app.services.stale_delivery_claims import recover_stale_delivery_claims
from app.worker import process_one


class EmbeddedWorker:
    """Bounded in-process worker pool for single-instance homologation.

    Atomic task claims and leases remain the concurrency boundary. Multiple consumers
    prevent one long AI delivery repair from starving every other project's final
    delivery while keeping concurrency deliberately small for the web-service runtime.
    """

    def __init__(self, poll_seconds: float = 2.0, concurrency: int | None = None) -> None:
        self.poll_seconds = max(0.05, float(poll_seconds))
        configured = concurrency if concurrency is not None else int(os.getenv("DEVPILOT_EMBEDDED_WORKER_CONCURRENCY", "3"))
        self.concurrency = max(1, min(int(configured), 4))
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._last_stale_recovery_at = 0.0

    @property
    def is_running(self) -> bool:
        return bool(self._threads) and all(thread.is_alive() for thread in self._threads)

    @property
    def _thread(self):
        """Compatibility view for older callers/tests expecting one thread."""
        return self._threads[0] if self._threads else None

    def start(self) -> None:
        if self.is_running:
            return

        runtime = worker_runtime_paths()
        print(
            "[embedded-worker] runtime OK: "
            + ", ".join(f"{tool}={path}" for tool, path in runtime.items())
            + f", concurrency={self.concurrency}",
            flush=True,
        )
        recovered = recover_stale_delivery_claims()
        if recovered:
            print(f"[embedded-worker] recovered stale delivery tasks={recovered}", flush=True)

        self._stop.clear()
        self._threads = []
        for index in range(self.concurrency):
            thread = threading.Thread(
                target=self._run,
                name=f"devpilot-embedded-worker-{index + 1}",
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

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
        for thread in tuple(self._threads):
            if thread.is_alive():
                thread.join(timeout=max(0.0, timeout))
        self._threads = []
