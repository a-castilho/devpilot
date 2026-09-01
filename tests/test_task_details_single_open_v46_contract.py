from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = (ROOT / "app/static/tasks-recovery-layout-v41.js").read_text(encoding="utf-8")
FEATURE = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_single_open_stays_inside_existing_tasks_bundle():
    tasks_start = FEATURE.index("tasks: [")
    tasks_end = FEATURE.index("tasksAnalytics:", tasks_start)
    tasks_bundle = FEATURE[tasks_start:tasks_end]

    assert "'tasks-recovery-layout-v41.js'" in tasks_bundle
    assert "task-details-single-open-v46.js" not in FEATURE


def test_runtime_enforces_exactly_one_visible_detail_row():
    assert "rows.forEach(row => setDetailRowState(row, row === keeper));" in LAYOUT
    assert "row.dataset.dpDetailsActive" in LAYOUT
    assert "row.dataset.dpV13Open" in LAYOUT
    assert "if (row.hidden === open) row.hidden = !open;" in LAYOUT
    assert "button.setAttribute('aria-expanded', open ? 'true' : 'false');" in LAYOUT


def test_runtime_reconciles_legacy_toggles_with_explicit_events():
    assert "window.addEventListener('click'" in LAYOUT
    assert "document.addEventListener('devpilot:tasks-rendered'" in LAYOUT
    assert "document.addEventListener('devpilot:view-changed'" in LAYOUT
    assert "document.addEventListener('devpilot:feature-ready'" in LAYOUT
    assert "[0, 24, 90].forEach" in LAYOUT
    assert "MutationObserver" not in LAYOUT


def test_css_has_final_authority_for_inactive_rows_and_wide_logs():
    assert '[data-task-details-row][data-dp-details-active="0"]' in LAYOUT
    assert "display:none!important;visibility:hidden!important" in LAYOUT
    assert ".tasks-v9-details-panel" in LAYOUT
    assert "overflow-wrap:anywhere!important" in LAYOUT
