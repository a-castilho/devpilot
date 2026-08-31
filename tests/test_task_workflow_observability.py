from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_task_workflow_observability_is_lazy_loaded_with_tasks():
    loader = (ROOT / "app/static/feature-loader.js").read_text()

    assert "task-workflow-observability.js" in loader
    assert "tasks: ['task-analytics.js'" in loader


def test_task_workflow_observability_reuses_protected_runner_health():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "api('/voice/runner-status')" in source
    assert "isSuperAdmin" in source
    assert "GitHub Actions Runner" in source
    assert "Infraestrutura protegida por RBAC" in source


def test_task_workflow_observability_separates_task_worker_from_github_runner():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "function taskWorkerHealth()" in source
    assert "Worker de tarefas ativo" in source
    assert "Fila aguardando worker" in source
    assert "a fila sozinha não prova falha do processo" in source
    assert "<b>Worker de tarefas</b>" in source
    assert "<b>GitHub Actions Runner</b>" in source
    assert "Runner ${escapeHtml(runnerLabel" not in source


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
    assert "Infraestrutura protegida por RBAC" in source
