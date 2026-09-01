from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_INDEX = ROOT / "app/static/game/index.html"
CLOUD_BRIDGE = ROOT / "app/delivery_cloud_bridge.py"
FINAL_SUMMARY = ROOT / "app/static/game/final-delivery-summary.js"


def test_isolated_game_loads_real_delivery_ui():
    html = GAME_INDEX.read_text(encoding="utf-8")
    assert "/assets/build-game-url-bonus.js" in html
    assert "/assets/game/final-delivery-summary.js" in html
    assert html.index("build-game-url-bonus.js") < html.index("game-bootstrap.js")


def test_delivery_validation_is_architecture_aware():
    source = CLOUD_BRIDGE.read_text(encoding="utf-8")
    assert "_adaptive_selected_providers" in source
    assert "_adaptive_verify" in source
    assert 'if "neon" in requested' in source
    assert 'if "render" in requested' in source
    assert 'if "vercel" in requested' in source
    assert 'f"{vercel_url}/health"' not in source
    assert '"name": "database"' in source
    assert 'neon.get("homolog_branch_id")' in source


def test_final_screen_explains_what_was_delivered():
    source = FINAL_SUMMARY.read_text(encoding="utf-8")
    assert "O QUE FOI ENTREGUE" in source
    assert "OBJETIVO" in source
    assert "entrega verificada" in source
    assert "URL entregue" in source
    assert "/tasks?project_id=" in source
    assert "/delivery`" in source
