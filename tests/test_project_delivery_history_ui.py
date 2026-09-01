from pathlib import Path


SCRIPT = Path("app/static/product-delivery-ui.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_projects_card_exposes_delivery_history_action():
    script = source()
    assert "Ver entrega" in script
    assert "product-delivery-history-action" in script
    assert "openDeliveryHistory(project)" in script


def test_delivery_history_uses_persisted_game_tasks():
    script = source()
    assert "[DEVPILOT_BUILD_GAME_V1]" in script
    assert "[DEVPILOT_DELIVERY_VERIFIER_V1]" in script
    assert "/tasks?project_id=" in script
    assert "PARTIDA" in script
    assert "OBJETIVO" in script
    assert "FASE" in script


def test_delivery_history_shows_all_six_phases_and_gate_state():
    script = source()
    assert "phase <= 6" in script
    assert "entrega verificada" in script
    assert "verificação pendente" in script


def test_delivery_history_shows_failure_and_real_url():
    script = source()
    assert "delivery?.last_error" in script
    assert "project-delivery-history-error" in script
    assert "project-delivery-history-url" in script
    assert "Abrir sistema ↗" in script
    assert "normalize(delivery?.status) === 'ready'" in script


def test_delivery_history_is_available_even_without_operator_role():
    script = source()
    history_pos = script.index("historyButton.textContent = 'Ver entrega'")
    operator_guard_pos = script.index("if (!canOperate()) return;", history_pos)
    assert history_pos < operator_guard_pos
