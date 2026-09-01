from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app" / "static" / "game" / "index.html"
DELIVERY_GATE_JS = ROOT / "app" / "static" / "game" / "delivery-gate.js"


def test_delivery_gate_is_loaded_before_game_bootstrap():
    html = GAME_HTML.read_text(encoding="utf-8")

    gate = html.index("/assets/game/delivery-gate.js")
    build_game = html.index("/assets/build-game.js")
    bootstrap = html.index("/assets/game/game-bootstrap.js")

    assert build_game < gate < bootstrap


def test_completed_execution_requires_independent_verifier_task():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")

    assert "[DEVPILOT_DELIVERY_VERIFIER_V1]" in script
    assert "normalize(latest.status) !== 'completed'" in script
    assert "Gate ${phaseId} · Verificar entrega real" in script
    assert "requires_approval: false" in script
    assert "Não aceite o status completed" in script


def test_verifier_requires_real_delivery_evidence():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")

    for requirement in (
        ".devpilot/build-game.md",
        "teste, lint/typecheck, build e smoke",
        "fluxo real",
        "schema/migração",
        "Delivery Target",
        "evidência reproduzível",
    ):
        assert requirement in script


def test_verifier_does_not_loop_after_successful_verification():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")

    assert "if (isVerifier(latest))" in script
    assert "if (normalize(latest.status) !== 'completed') break;" in script
    assert "continue;" in script
