from __future__ import annotations

from types import SimpleNamespace

from app.services import delivery_recovery_worker as worker


class _Rows:
    def __init__(self, values):
        self.values = values

    def all(self):
        return list(self.values)


class _Db:
    def __init__(self, project):
        self.project = project
        self.commits = 0
        self.rollbacks = 0

    def scalars(self, _query):
        return _Rows([self.project])

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def get(self, _model, project_id):
        return self.project if project_id == self.project.id else None


def _project():
    return SimpleNamespace(
        id="project-1",
        workspace_id="workspace-1",
        repository_url="https://github.com/acme/demo",
        codex_config="{}",
    )


def _install_delivery_fakes(monkeypatch, state, run):
    monkeypatch.setattr(worker.delivery, "initial_delivery", lambda _project: state)
    monkeypatch.setattr(worker.delivery, "save_delivery", lambda _db, _project, _state: None)
    monkeypatch.setattr(worker.delivery, "run_delivery", run)
    monkeypatch.setattr(worker, "record", lambda *_args, **_kwargs: None)


def test_pending_delivery_starts_after_latest_phase_7_gate(monkeypatch):
    project = _project()
    db = _Db(project)
    state = {"status": "pending", "url": ""}
    calls = []

    _install_delivery_fakes(
        monkeypatch,
        state,
        lambda _db, _project, actor: calls.append(actor)
        or {"status": "ready", "url": "https://demo.vercel.app"},
    )
    monkeypatch.setattr(worker, "_final_gate_completed", lambda *_args: True)

    assert worker.process_one_pending_delivery(db) is True
    assert calls == ["system:delivery-recovery"]


def test_pending_delivery_does_not_start_before_phase_7_gate(monkeypatch):
    project = _project()
    db = _Db(project)
    state = {"status": "pending", "url": ""}
    calls = []

    _install_delivery_fakes(
        monkeypatch,
        state,
        lambda *_args: calls.append(True) or state,
    )
    monkeypatch.setattr(worker, "_final_gate_completed", lambda *_args: False)

    assert worker.process_one_pending_delivery(db) is False
    assert calls == []


def test_blocked_delivery_is_retried_without_browser(monkeypatch):
    project = _project()
    db = _Db(project)
    state = {"status": "blocked", "url": "", "last_error": "cloud"}

    _install_delivery_fakes(
        monkeypatch,
        state,
        lambda _db, _project, _actor: {"status": "ready", "url": "https://demo.vercel.app"},
    )

    assert worker.process_one_pending_delivery(db) is True


def test_recovery_backoff_prevents_hot_loop(monkeypatch):
    project = _project()
    db = _Db(project)
    state = {
        "status": "deploying",
        "recovery_next_at": "2999-01-01T00:00:00+00:00",
    }

    _install_delivery_fakes(monkeypatch, state, lambda *_args: state)

    assert worker.process_one_pending_delivery(db) is False


def test_provider_exception_is_scheduled_instead_of_killing_worker(monkeypatch):
    project = _project()
    db = _Db(project)
    state = {"status": "failed", "url": ""}

    def explode(*_args):
        raise RuntimeError("provider temporarily unavailable")

    _install_delivery_fakes(monkeypatch, state, explode)

    assert worker.process_one_pending_delivery(db) is True
    assert db.rollbacks == 1
    assert state.get("recovery_owner") == "worker"
    assert "provider temporarily unavailable" in state.get("recovery_last_error", "")


def test_worker_entry_and_embedded_worker_run_delivery_recovery_every_cycle():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    dedicated = (root / "app/worker_entry.py").read_text(encoding="utf-8")
    embedded = (root / "app/embedded_worker.py").read_text(encoding="utf-8")

    assert "delivery_processed = process_one_pending_delivery(db)" in dedicated
    assert "delivery_processed = process_one_pending_delivery(db)" in embedded
    assert "not rag_processed and not delivery_processed and not task_processed" in dedicated
    assert "not task_processed and not delivery_processed" in embedded
