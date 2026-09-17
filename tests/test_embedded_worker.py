import threading

from app.embedded_worker import EmbeddedWorker


def test_embedded_worker_processes_queue_and_stops(monkeypatch):
    processed = threading.Event()
    monkeypatch.setattr("app.embedded_worker.worker_runtime_paths", lambda: {"git": "/usr/bin/git", "codex": "/usr/local/bin/codex"})
    def fake_process_one():
        processed.set()
        return False
    monkeypatch.setattr("app.embedded_worker.process_one", fake_process_one)
    worker = EmbeddedWorker(poll_seconds=0.01)
    worker.start()
    assert processed.wait(1.0)
    assert worker.is_running
    worker.stop(timeout=1.0)
    assert not worker.is_running


def test_embedded_worker_start_is_idempotent(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    monkeypatch.setattr("app.embedded_worker.worker_runtime_paths", lambda: {"git": "/usr/bin/git", "codex": "/usr/local/bin/codex"})
    def fake_process_one():
        entered.set()
        release.wait(1.0)
        return False
    monkeypatch.setattr("app.embedded_worker.process_one", fake_process_one)
    worker = EmbeddedWorker(poll_seconds=0.01)
    worker.start()
    assert entered.wait(1.0)
    first_threads = tuple(worker._threads)
    worker.start()
    assert tuple(worker._threads) == first_threads
    release.set()
    worker.stop(timeout=1.0)


def test_embedded_worker_defaults_to_one_database_safe_consumer(monkeypatch):
    monkeypatch.delenv("DEVPILOT_EMBEDDED_WORKER_CONCURRENCY", raising=False)
    worker = EmbeddedWorker(poll_seconds=0.01)
    assert worker.concurrency == 1


def test_embedded_worker_can_use_explicit_bounded_parallel_consumers(monkeypatch):
    entered = set(); lock = threading.Lock(); all_entered = threading.Event(); release = threading.Event()
    monkeypatch.setattr("app.embedded_worker.worker_runtime_paths", lambda: {"git": "/usr/bin/git", "codex": "/usr/local/bin/codex"})
    def fake_process_one():
        with lock:
            entered.add(threading.get_ident())
            if len(entered) >= 3: all_entered.set()
        release.wait(1.0)
        return False
    monkeypatch.setattr("app.embedded_worker.process_one", fake_process_one)
    worker = EmbeddedWorker(poll_seconds=0.01, concurrency=3)
    worker.start()
    assert all_entered.wait(1.0)
    assert len(worker._threads) == 3
    release.set()
    worker.stop(timeout=1.0)
