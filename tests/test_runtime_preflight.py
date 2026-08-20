from __future__ import annotations

import pytest

import app.services.runtime_preflight as runtime_preflight
import app.worker as worker


def test_worker_runtime_requires_git_and_codex(monkeypatch):
    paths = {"git": "/usr/bin/git", "codex": "/usr/local/bin/codex"}
    monkeypatch.setattr(runtime_preflight, "which", paths.get)

    assert runtime_preflight.worker_runtime_paths() == paths


def test_worker_runtime_reports_missing_tool_without_processing_task(monkeypatch):
    monkeypatch.setattr(
        runtime_preflight,
        "which",
        lambda tool: "/usr/local/bin/codex" if tool == "codex" else None,
    )

    with pytest.raises(runtime_preflight.WorkerRuntimeError, match="git"):
        runtime_preflight.worker_runtime_paths()


def test_worker_exits_before_consuming_queue_when_runtime_is_incomplete(monkeypatch):
    consumed = False

    def fail_preflight():
        raise runtime_preflight.WorkerRuntimeError("Ferramentas ausentes: git")

    def process_one():
        nonlocal consumed
        consumed = True
        return False

    monkeypatch.setattr(worker, "worker_runtime_paths", fail_preflight)
    monkeypatch.setattr(worker, "process_one", process_one)

    with pytest.raises(SystemExit) as caught:
        worker.main()

    assert caught.value.code == 78
    assert consumed is False
