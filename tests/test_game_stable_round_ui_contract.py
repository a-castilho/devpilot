from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE = ROOT / "app/static/game/stable-round-ui.js"
BOOT = ROOT / "app/static/game/game-bootstrap.js"
INDEX = ROOT / "app/static/game/index.html"


def test_active_round_surface_lives_outside_polling_target():
    source = STABLE.read_text(encoding="utf-8")
    assert "devpilot-game-stable-round-v84" in source
    assert "document.querySelector('.devpilot-game-stage')" in source
    assert "target.style.setProperty('display', detailsOpen ? 'block' : 'none', 'important')" in source
    assert "if (nextSignature === lastSignature) return true" in source


def test_bootstrap_loads_stable_ui_and_uses_one_revision():
    boot = BOOT.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")
    assert "game/stable-round-ui.js" in boot
    assert "game-flow-v84-20260903" in boot
    assert "game-flow-v84-20260903" in html
    assert "unified-v84" in boot


def run_contract():
    test_active_round_surface_lives_outside_polling_target()
    test_bootstrap_loads_stable_ui_and_uses_one_revision()
    print("GAME_STABLE_ROUND_UI=OK")


if __name__ == "__main__":
    run_contract()
