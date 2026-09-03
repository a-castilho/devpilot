from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_execution_details_click_keeps_accessibility_state_in_sync():
    focus = (ROOT / "app/static/executions-focus-v19.js").read_text(encoding="utf-8")
    recovery = (ROOT / "app/static/tasks-recovery-layout-v41.js").read_text(encoding="utf-8")
    operational = (ROOT / "app/static/tasks-operational-ui.js").read_text(encoding="utf-8")

    # V41 usa aria-hidden como parte da decisão de manter o detalhe aberto.
    assert "row.getAttribute('aria-hidden') === 'true'" in recovery

    # O renderer operacional abre/fecha pela propriedade hidden/display.
    assert "const opening = row.hidden" in operational
    assert "row.hidden = false" in operational

    # A ponte roda em bubble phase, depois do onclick do renderer e antes dos
    # timers de reconciliação agendados em capture phase.
    assert "function syncDetailsStateAfterClick(event)" in focus
    assert ".tasks-v9-details[data-id]" in focus
    assert ".task-instructions-load[data-id]" in focus
    assert "const open = !row.hidden" in focus
    assert "row.setAttribute('aria-hidden', open ? 'false' : 'true')" in focus
    assert "row.dataset.dpDetailsActive = open ? '1' : '0'" in focus
    assert "document.addEventListener('click', syncDetailsStateAfterClick, false)" in focus


if __name__ == "__main__":
    test_execution_details_click_keeps_accessibility_state_in_sync()
    print("EXECUTION DETAILS CLICK: contrato OK")
