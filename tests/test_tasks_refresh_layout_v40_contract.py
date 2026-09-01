from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_UPLOAD = (ROOT / "app/static/task-image-upload.js").read_text(encoding="utf-8")
FEATURE_LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
TASK_FAILURES = (ROOT / "app/static/task-failures.js").read_text(encoding="utf-8")


def test_stability_guard_runs_after_legacy_failure_renderer():
    failure_index = FEATURE_LOADER.index("'task-failures.js'")
    stability_host_index = FEATURE_LOADER.index("'task-image-upload.js'")
    assert stability_host_index > failure_index
    assert "__devpilotTasksRenderStabilityV40" in IMAGE_UPLOAD
    assert "installRendererGuard" in IMAGE_UPLOAD
    assert "stableRenderTasksV40" in IMAGE_UPLOAD


def test_legacy_five_column_rows_are_normalized_to_current_execution_contract():
    assert "tasks-render-stable-v40" in IMAGE_UPLOAD
    assert "cells[0].classList.add('tasks-v9-main')" in IMAGE_UPLOAD
    assert "cells[1].classList.add('tasks-v9-source')" in IMAGE_UPLOAD
    assert "cells[2].classList.add('tasks-v9-state')" in IMAGE_UPLOAD
    assert "cells[3].classList.add('tasks-v9-priority')" in IMAGE_UPLOAD
    assert "cells[4].classList.add('tasks-v9-actions')" in IMAGE_UPLOAD
    assert "grid-template-columns:minmax(0,1fr) minmax(180px,280px)!important" in IMAGE_UPLOAD
    assert "word-break:normal!important" in IMAGE_UPLOAD


def test_refresh_keeps_failure_diagnostics_without_letting_failure_renderer_own_layout():
    assert "renderTasks = function renderTasksWithFailureDetails()" in TASK_FAILURES
    assert "const result = upstream.apply(this, args)" in IMAGE_UPLOAD
    assert "normalizeRows();" in IMAGE_UPLOAD
    assert "requestAnimationFrame(() => normalizeRows({emit:false}))" in IMAGE_UPLOAD


def test_recovery_tasks_are_identified_and_cannot_recursively_show_recover_action():
    assert "failure-recovery" in IMAGE_UPLOAD
    assert "tasks-v9-recovery-row" in IMAGE_UPLOAD
    assert "kind.textContent = 'Recuperação'" in IMAGE_UPLOAD
    assert ".tasks-v9-recovery-row .task-recovery-action" in IMAGE_UPLOAD
    assert ".forEach(button => button.remove())" in IMAGE_UPLOAD


def test_normalized_rows_reemit_tasks_rendered_for_existing_enhancements():
    assert "new CustomEvent('devpilot:tasks-rendered'" in IMAGE_UPLOAD
    assert "stabilityV40:true" in IMAGE_UPLOAD
    assert "if (event.detail?.stabilityV40) return" in IMAGE_UPLOAD
