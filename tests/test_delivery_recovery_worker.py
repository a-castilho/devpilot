from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services import delivery_recovery_worker as worker


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _FakeDb:
    def __init__(self, projects):
        self.projects = projects
        self.commits = 0
        self.rollbacks = 0

    def scalars(self, _statement):
        return _Scalars(self.projects)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def get(self, _model, project_id):
        return next((item for item in self.projects if item.id == project_id), None)


def _project():
    return SimpleNamespace(
        id="project-1",
        workspace_id="workspace-1",
        repository_url="https://github.com/example/project",
    )


def test_blocked_delivery_is_retried_by_worker_and_can_finish_with_url(monkeypatch):
    project = _project()
    db = _FakeDb([project])
    saved = []
    calls = []
    states = {
        project.id: {
            "status": "blocked",
            "delivery_gate": "waiting_for_testable_url",
            "url": "",
        }
    }

    monkeypatch.setattr(worker.delivery, "initial_delivery", lambda current: dict(states[current.id]))

    def save_delivery(_db, current, state):
        states[current.id] = dict(state)
        saved.append(dict(state))

    monkeypatch.setattr(worker.delivery, "save_delivery", save_delivery)

    def run_delivery(_db, current, actor):
        calls.append((current.id, actor))
        return {
            **states[current.id],
            "status": "ready",
            "delivery_gate": "delivered",
            "url": "https://produto.vercel.app",
        }

    monkeypatch.setattr(worker.delivery, "run_delivery", run_delivery)
    monkeypatch.setattr(worker, "record", lambda *_args, **_kwargs: None)

    processed = worker.process_one_pending_delivery(
        db,
        now=datetime(2026, 9, 14, 21, 30, tzinfo=timezone.utc),
    )

    assert processed is True
    assert calls == [("project-1", "system:delivery-recovery")]
    assert states[project.id]["status"] == "ready"
    assert states[project.id]["url"] == "https://produto.vercel.app"
    assert states[project.id]["recovery_next_at"] == ""
    assert saved


def test_recovery_respects_persisted_backoff(monkeypatch):
    project = _project()
    db = _FakeDb([project])
    now = datetime(2026, 9, 14, 21, 30, tzinfo=timezone.utc)
    state = {
        "status": "blocked",
        "delivery_gate": "waiting_for_testable_url",
        "recovery_next_at": (now + timedelta(minutes=2)).isoformat(),
    }

    monkeypatch.setattr(worker.delivery, "initial_delivery", lambda _project: dict(state))
    monkeypatch.setattr(
        worker.delivery,
        "run_delivery",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not retry before backoff")),
    )

    assert worker.process_one_pending_delivery(db, now=now) is False


def test_provider_failure_schedules_retry_without_crashing_worker(monkeypatch):
    project = _project()
    db = _FakeDb([project])
    states = {project.id: {"status": "failed", "url": ""}}

    monkeypatch.setattr(worker.delivery, "initial_delivery", lambda current: dict(states[current.id]))
    monkeypatch.setattr(
        worker.delivery,
        "save_delivery",
        lambda _db, current, state: states.__setitem__(current.id, dict(state)),
    )
    monkeypatch.setattr(worker.delivery, "run_delivery", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider timeout")))
    monkeypatch.setattr(worker, "record", lambda *_args, **_kwargs: None)

    processed = worker.process_one_pending_delivery(
        db,
        now=datetime(2026, 9, 14, 21, 30, tzinfo=timezone.utc),
    )

    assert processed is True
    assert db.rollbacks == 1
    assert "provider timeout" in states[project.id]["recovery_last_error"]
    assert states[project.id]["recovery_next_at"]


def test_worker_entry_and_embedded_worker_do_not_depend_on_browser_for_delivery():
    worker_entry = open("app/worker_entry.py", encoding="utf-8").read()
    embedded = open("app/embedded_worker.py", encoding="utf-8").read()

    assert "process_one_pending_delivery" in worker_entry
    assert "process_one_pending_delivery" in embedded
    assert "SessionLocal" in embedded
