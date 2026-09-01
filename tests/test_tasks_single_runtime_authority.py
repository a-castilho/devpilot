from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTIONS = (ROOT / "app/static/executions-v18.js").read_text(encoding="utf-8")
FEATURES = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
OPERATIONAL = (ROOT / "app/static/tasks-operational-ui.js").read_text(encoding="utf-8")


def test_shell_installs_single_tasks_runtime_authority() -> None:
    assert "guardedRenderTasks" in EXECUTIONS
    assert "__devpilotLegacyRenderTasks" in EXECUTIONS
    assert "__devpilotTasksOperationalV9" in EXECUTIONS
    assert "__devpilotLoadFeature('tasks')" in EXECUTIONS
    assert "window.renderTasks = guardedRenderTasks" in EXECUTIONS


def test_legacy_tasks_stylesheet_is_not_kept_in_parallel_runtime() -> None:
    assert "devpilot-task-development-v2" in EXECUTIONS
    assert "document.getElementById('devpilot-task-development-v2')?.remove()" in EXECUTIONS


def test_tasks_bundle_keeps_operational_renderer_as_first_owner() -> None:
    tasks_bundle = FEATURES.split("tasks: [", 1)[1].split("],", 1)[0]
    assert tasks_bundle.index("'tasks-operational-ui.js'") < tasks_bundle.index("'project-delete-ui.js'")
    assert "window.renderTasks = renderOperationalTasks" in OPERATIONAL


def test_runtime_authority_adopts_operational_renderer_after_feature_ready() -> None:
    assert "adoptOperationalRenderer" in EXECUTIONS
    assert "event.detail?.feature === 'tasks'" in EXECUTIONS
    assert "devpilotTasksRuntime = 'operational-v9'" in EXECUTIONS


def test_guard_never_renders_legacy_five_column_markup() -> None:
    guarded = EXECUTIONS.split("function guardedRenderTasks()", 1)[1].split("function installSingleRuntimeAuthority()", 1)[0]
    assert 'colspan="5"' not in guarded
    assert "task-secondary-cell" not in guarded
    assert "task-priority-cell" not in guarded
