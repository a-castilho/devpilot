from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app/static/game/index.html"
SCRIPT = ROOT / "app/static/game/delivery-resilience.js"


def test_delivery_resilience_is_loaded_before_game_bootstrap():
    html = INDEX.read_text(encoding="utf-8")
    assert "/assets/game/delivery-resilience.js" in html
    assert html.index("delivery-resilience.js") < html.index("game-bootstrap.js")


def test_delivery_mutations_use_long_timeout_and_recover_authoritative_state():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "LONG_DELIVERY_TIMEOUT_MS = 60_000" in source
    assert "client_request_recovered" in source
    assert "/delivery`" in source or "/delivery'" in source or "/delivery\"" in source
    assert "repair_exhausted" in source
    assert "repairing_product" in source
    assert "AUTOCORREÇÃO ATIVA" in source
