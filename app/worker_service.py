from __future__ import annotations

import os
import threading

from fastapi import FastAPI

from app.services.runtime_preflight import WorkerRuntimeError, worker_runtime_paths
from app.worker import process_one

app = FastAPI(title="DevPilot Worker")
_stop = threading.Event()
_thread: threading.Thread | None = None
_runtime: dict[str, str] = {}
_error = ""


def _loop() -> None:
    global _error
    while not _stop.is_set():
        try:
            processed = process_one()
            _error = ""
        except Exception as exc:  # defensive: keep the worker process alive
            _error = str(exc)[:1000]
            processed = False
        if not processed:
            _stop.wait(2.0)


@app.on_event("startup")
def startup() -> None:
    global _thread, _runtime, _error
    try:
        _runtime = worker_runtime_paths()
    except WorkerRuntimeError as exc:
        _error = str(exc)
        return
    _thread = threading.Thread(target=_loop, name="devpilot-worker", daemon=True)
    _thread.start()


@app.on_event("shutdown")
def shutdown() -> None:
    _stop.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=5)


@app.get("/health")
def health() -> dict:
    running = bool(_thread and _thread.is_alive())
    return {
        "status": "ok" if running else "degraded",
        "service": "devpilot-worker",
        "running": running,
        "runtime": _runtime,
        "error": _error or None,
        "execution_enabled": os.getenv("DEVPILOT_EXECUTION_ENABLED", "").lower() in {"1", "true", "yes", "on"},
    }
