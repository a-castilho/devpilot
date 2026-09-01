from pathlib import Path


SCRIPT = Path("app/static/product-delivery-ui.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_delivery_button_is_visible_and_explicit():
    text = source()
    assert "📦 Ver entrega" in text
    assert "product-delivery-history-action" in text
    assert "display:inline-flex!important" in text
    assert "visibility:visible!important" in text


def test_delivery_button_survives_project_card_rerender():
    text = source()
    assert "MutationObserver" in text
    assert "observer.observe(host, {childList:true, subtree:true})" in text
    assert "decorateAll(false)" in text
    assert "devpilot:feature-ready" in text


def test_delivery_history_still_reads_persisted_game_tasks():
    text = source()
    assert "[DEVPILOT_BUILD_GAME_V1]" in text
    assert "PARTIDA" in text
    assert "OBJETIVO" in text
    assert "FASE" in text
    assert "/tasks?project_id=" in text
    assert "/delivery" in text
    assert "Abrir sistema ↗" in text
