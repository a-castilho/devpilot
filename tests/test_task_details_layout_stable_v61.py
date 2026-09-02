from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURE = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
TASKS = (ROOT / "app/static/tasks-operational-ui.js").read_text(encoding="utf-8")
LAYOUT = (ROOT / "app/static/tasks-recovery-layout-v41.js").read_text(encoding="utf-8")


def _bundle(name: str, next_name: str) -> str:
    start = FEATURE.index(f"{name}: [")
    end = FEATURE.index(f"{next_name}:", start)
    return FEATURE[start:end]


def test_details_bundle_is_local_and_cannot_swap_global_task_renderer():
    details = _bundle("tasksDetails", "tasksEnhancements")

    assert "'execution-results-v28.js'" in details
    assert "'task-completion-documentation.js'" not in details
    assert "'task-failures.js'" not in details
    assert "'task-image-upload.js'" not in details


def test_global_action_enhancement_is_ready_before_tasks_view_becomes_interactive():
    tasks = _bundle("tasks", "tasksAnalytics")

    assert "'tasks-operational-ui.js'" in tasks
    assert "'tasks-recovery-layout-v41.js'" in tasks
    assert "'task-completion-documentation.js'" in tasks


def test_legacy_diagnostics_are_not_triggered_by_details_click():
    enhancements = _bundle("tasksEnhancements", "reports")
    details = _bundle("tasksDetails", "tasksEnhancements")

    assert "'task-failures.js'" in enhancements
    assert "'task-image-upload.js'" in enhancements
    assert "task-failures.js" not in details
    assert "task-image-upload.js" not in details


def test_operational_details_toggle_only_the_clicked_row_without_rerendering_list():
    start = TASKS.index("async function toggleDetails(button)")
    end = TASKS.index("async function approveTask", start)
    toggle = TASKS[start:end]

    assert 'document.querySelector(`[data-task-details-row=' in toggle
    assert "document.querySelectorAll('.task-details-row:not([hidden])')" in toggle
    assert "if (other === row) return;" in toggle
    assert "row.hidden = false;" in toggle
    assert "button.setAttribute('aria-expanded', 'true');" in toggle
    assert "renderOperationalTasks()" not in toggle
    assert "reloadTasks(" not in toggle


def test_existing_single_open_contract_remains_authoritative():
    assert "view.dataset.dpDetailsSingleOpen = '1';" in LAYOUT
    assert "rows.forEach(row => setDetailRowState(row, row === keeper));" in LAYOUT
    assert '[data-task-details-row][data-dp-details-active="0"]' in LAYOUT
