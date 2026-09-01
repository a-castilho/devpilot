from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAV = (ROOT / "app/static/page-navigation-v26.js").read_text(encoding="utf-8")
JS = (ROOT / "app/static/task-details-single-open-v46.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/task-details-single-open-v46.css").read_text(encoding="utf-8")


def test_single_open_assets_are_loaded_after_execution_ship_layer():
    assert "/assets/task-details-single-open-v46.css?v=20260901-1" in NAV
    assert "/assets/task-details-single-open-v46.js?v=20260901-1" in NAV
    assert NAV.index("devpilot-execution-ship-v45") < NAV.index("devpilot-task-details-single-open-v46")


def test_runtime_enforces_exactly_one_visible_detail_row():
    assert "allRows.forEach(row => setRowState(row, row === keeper));" in JS
    assert "row.dataset.dpDetailsActive" in JS
    assert "row.dataset.dpV13Open" in JS
    assert "row.hidden = !open" in JS
    assert "buttonsFor(id).forEach(button => syncButton(button, open));" in JS


def test_runtime_reconciles_legacy_toggles_and_rerenders():
    assert "window.addEventListener('click'" in JS
    assert "new MutationObserver" in JS
    assert "document.addEventListener('devpilot:tasks-rendered'" in JS
    assert "[0, 24, 90].forEach" in JS


def test_css_has_final_authority_for_inactive_rows_and_wide_logs():
    assert '[data-task-details-row][data-dp-details-active="0"]' in CSS
    assert "display:none !important" in CSS
    assert "visibility:hidden !important" in CSS
    assert ".tasks-v9-details-panel" in CSS
    assert "overflow-wrap:anywhere !important" in CSS
