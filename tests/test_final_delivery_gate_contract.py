from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
GATE = (ROOT / "app/static/game/final-delivery-gate.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/acs-loader.js").read_text(encoding="utf-8")


def test_final_delivery_gate_is_loaded_after_url_bridge():
    assert "game/stable-delivery-url.js','game/final-delivery-gate.js'" in BOOTSTRAP
    assert "game-flow-v93-20260913" in BOOTSTRAP


def test_final_delivery_gate_never_marks_pending_delivery_as_complete():
    assert "deliveryUrlReady === '1'" in GATE
    assert "Finalizando a entrega" in GATE
    assert "Publicando e validando URL" in GATE
    assert "newRound.hidden = true" in GATE
    assert "newRound.disabled = true" in GATE


def test_legacy_duplicate_final_card_is_suppressed():
    assert "devpilotLegacyFinalSuppressed" in GATE
    assert "Entrega concluída|Entrega pronta|MISSÃO CUMPRIDA" in GATE
    assert "display', 'none', 'important'" in GATE


def test_login_loader_requires_application_readiness_not_health_only():
    assert "checkApplicationReadiness" in LOADER
    assert "'/api/auth/status'" in LOADER
    assert "consecutiveReady >= 2" in LOADER
    assert "Confirmando autenticação e banco" in LOADER
