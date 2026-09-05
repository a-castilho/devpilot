from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_task_workflow_observability_is_lazy_loaded_with_tasks():
    loader = (ROOT / "app/static/feature-loader.js").read_text()
    tasks_bundle = loader.split("tasks: [", 1)[1].split("tasksAnalytics:", 1)[0]

    assert "'task-workflow-observability.js'" in tasks_bundle
    assert "tasksAnalytics: ['task-analytics.js']" in loader


def test_task_workflow_observability_reuses_protected_runner_health():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "api('/voice/runner-status')" in source
    assert "isSuperAdmin" in source
    assert "restritas ao Super Admin" in source
    assert "nenhum estado é presumido" in source


def test_task_workflow_observability_reuses_task_identity_and_has_no_global_observer():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()
    task_modal = (ROOT / "app/static/task-modal.js").read_text()

    assert "row.dataset.taskId" in task_modal
    assert "row.dataset.taskId || tasks[index]?.id" in source
    assert "__devpilotTaskWorkflowObservabilityReady" in source
    assert "MutationObserver" not in source


def test_task_workflow_observability_correlates_existing_run_evidence():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()
    routes = (ROOT / "app/task_run_routes.py").read_text()

    assert "api('/task-runs/latest?limit=100')" in source
    assert "api(`/task-runs/${encodeURIComponent(runId)}`)" in source
    assert "commit_sha" in source
    assert "pull_request_url" in source
    assert '"commit_sha": run.commit_sha' in routes
    assert '"pull_request_url": run.pull_request_url' in routes


def test_task_workflow_observability_does_not_eager_load_runner_for_regular_users():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "if (!canSeeRunner()) return null" in source
    assert "infraestrutura protegida por RBAC" in source
