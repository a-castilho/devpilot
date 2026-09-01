from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(path: str) -> str:
    return (STATIC / path).read_text(encoding="utf-8")


def test_tasks_recovery_layout_enforces_only_one_open_detail():
    source = read("tasks-recovery-layout-v41.js")
    assert "let activeDetailId = ''" in source
    assert "function enforceSingleOpenDetail" in source
    assert "function closeDetailElement" in source
    assert "activeDetailId = expanded ? id : ''" in source
    assert "enforceSingleOpenDetail(activeDetailId)" in source
    assert '.task-details-row[hidden]' in source


def test_execution_result_technical_log_starts_collapsed():
    source = read("execution-results-v28.js")
    assert '<details class="dp-v28-output">' in source
    assert '<details class="dp-v28-output" open>' not in source


def test_detail_scope_is_bound_to_task_id():
    source = read("tasks-recovery-layout-v41.js")
    assert 'data-task-details-row="${safe}"' in source
    assert 'tasks-v9-details[data-id="${safe}"]' in source
    assert "element.dataset.taskDetailsRow || element.dataset.taskInstructions" in source
