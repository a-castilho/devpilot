from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "app/static/game/stable-delivery-url.js"
BOOT = ROOT / "app/static/game/game-bootstrap.js"


def test_stable_delivery_asset_is_loaded_with_round_ui():
    boot = BOOT.read_text(encoding="utf-8")
    assert "game/stable-round-ui.js" in boot
    assert "game/stable-delivery-url.js" in boot
    assert boot.index("game/stable-round-ui.js") < boot.index("game/stable-delivery-url.js")


def test_final_round_requires_validated_https_url_before_completion():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "normalized(delivery) === 'ready'" in source
    assert r"/^https:\/\//i" in source
    assert "Finalizando a entrega" in source
    assert "A missão só será marcada como entregue quando uma URL HTTPS real estiver validada." in source
    assert "newRound.hidden = true" in source
    assert "newRound.hidden = false" in source


def test_final_round_exposes_clickable_project_url_when_ready():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "URL DO PROJETO" in source
    assert "Projeto disponível para teste" in source
    assert "stable-delivery-url-value" in source
    assert "Abrir projeto ↗" in source
    assert 'target="_blank"' in source
    assert 'rel="noopener noreferrer"' in source


def test_final_round_is_get_only_observer():
    source = DELIVERY.read_text(encoding="utf-8")
    assert "WATCH_MS = 30000" in source
    assert "/delivery/start" not in source
    assert "/delivery/retry" not in source
    assert "/delivery/validate-url" not in source
    assert "method: 'POST'" not in source
    assert "document.visibilityState" in source
    assert "backend continua a recuperação" in source.lower()


def run_contract():
    test_stable_delivery_asset_is_loaded_with_round_ui()
    test_final_round_requires_validated_https_url_before_completion()
    test_final_round_exposes_clickable_project_url_when_ready()
    test_final_round_is_get_only_observer()
    print("GAME_STABLE_DELIVERY_URL=OK")


if __name__ == "__main__":
    run_contract()
