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
    assert "restritas ao Super Admin" in source
    assert "nenhum estado é presumido" in source
    assert "nenhum sucesso é inferido" in source


def test_task_workflow_observability_reuses_task_identity_and_is_idempotent():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()
    task_modal = (ROOT / "app/static/task-modal.js").read_text()

    assert "row.dataset.taskId" in task_modal
    assert "row.dataset.taskId || tasks[index]?.id" in source
    assert "__devpilotTaskWorkflowObservabilityReady" in source
    assert "MutationObserver" in source


def test_task_workflow_observability_does_not_eager_load_runner_for_regular_users():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "if (!canSeeRunner()) return null" in source
    assert "infraestrutura protegida por RBAC" in source
