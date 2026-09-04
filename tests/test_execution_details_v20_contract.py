from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/executions-focus-v19.js").read_text(encoding="utf-8")


def test_execution_details_click_materializes_open_state():
    assert "window.__devpilotExecutionsFocusV20" in JS
    assert "function forceDetailState(view, id, open)" in JS
    assert "row.hidden = !open" in JS
    assert "row.dataset.dpDetailsActive = open ? '1' : '0'" in JS
    assert "row.dataset.dpV13Open = open ? '1' : '0'" in JS
    assert "row.style.setProperty('display', open ? 'block' : 'none', 'important')" in JS


def test_execution_details_closes_other_rows_and_survives_reconcile_frame():
    assert "otherId !== id" in JS
    assert "forceDetailState(view, otherId, false)" in JS
    assert "[0, 32, 120].forEach" in JS
    assert "document.addEventListener('click', syncDetailsStateAfterClick, false)" in JS


def test_execution_details_does_not_add_polling_loop():
    assert "setInterval" not in JS
    assert "MutationObserver" not in JS
