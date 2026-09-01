from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def read(path: str) -> str:
    return (STATIC / path).read_text(encoding="utf-8")


def test_standalone_game_loads_neon_layout_after_inline_approval():
    html = read("game/index.html")
    assert "game/neon-layout.css?v=game-v49-20260901" in html
    assert "game/inline-approval.js?v=game-v49-20260901" in html
    assert "game/neon-layout.js?v=game-v49-20260901" in html
    assert html.index("game/inline-approval.js") < html.index("game/neon-layout.js")
    assert html.index("game/neon-layout.js") < html.index("game/game-bootstrap.js")


def test_neon_layout_keeps_real_game_states_and_inline_approval():
    script = read("game/neon-layout.js")
    assert "build-game-phase.current" in script
    assert "build-game-phase.passed" in script
    assert "AWAITING APPROVAL" in script
    assert "data-game-inline-approve" in read("game/inline-approval.js")
    assert "window.loadBuildGame" in script
    assert "Continuar" in script


def test_neon_mobile_has_mission_phase_xp_and_bottom_navigation():
    script = read("game/neon-layout.js")
    css = read("game/neon-layout.css")
    for token in (
        "MISSÃO ATIVA",
        "devpilot-game-xp-badge",
        "game-neon-phase-number",
        "game-neon-bottom-nav",
        "Projetos",
        "Execuções",
    ):
        assert token in script or token in css


def test_neon_runtime_disables_expensive_blur_in_served_document():
    html = read("game/index.html")
    assert "backdrop-filter:none!important" in html
    assert "@media(min-width:901px)" in html
    assert "game-neon-bottom-nav{display:none!important}" in html
