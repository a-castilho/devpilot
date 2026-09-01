from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "app/static/tasks-recovery-layout-v41.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_recovery_layout_is_loaded_after_recovery_flow():
    recovery = LOADER.index("'task-recovery-flow.js'")
    layout = LOADER.index("'tasks-recovery-layout-v41.js'")
    assert recovery < layout


def test_internal_recovery_tasks_are_hidden_from_operational_list():
    assert "INTERNAL_SOURCES = new Set(['failure-recovery'])" in SCRIPT
    assert 'data-devpilot-internal-task' in SCRIPT
    assert "operational = allTasks.filter(task => !isInternal(task))" in SCRIPT


def test_layout_uses_real_container_width_instead_of_only_viewport_breakpoints():
    assert "ResizeObserver" in SCRIPT
    assert "getBoundingClientRect().width" in SCRIPT
    assert "width < 760" in SCRIPT
    assert "tasks-v41-compact" in SCRIPT


def test_wide_rows_keep_title_status_and_actions_in_stable_columns():
    assert "grid-template-columns:minmax(260px,1fr) minmax(108px,142px) minmax(148px,max-content)" in SCRIPT
    assert ".tasks-v9-main{grid-column:1!important" in SCRIPT
    assert ".tasks-v9-state{grid-column:2!important" in SCRIPT
    assert ".tasks-v9-actions{grid-column:3!important" in SCRIPT


def test_compact_rows_stack_without_letter_by_letter_breaking():
    assert "grid-template-columns:minmax(0,1fr) auto" in SCRIPT
    assert "word-break:normal!important" in SCRIPT
    assert "overflow-wrap:break-word!important" in SCRIPT
    assert "white-space:normal!important" in SCRIPT
