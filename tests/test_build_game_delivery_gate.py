from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME_HTML = ROOT / "app" / "static" / "game" / "index.html"
BOOTSTRAP_JS = ROOT / "app" / "static" / "game" / "game-bootstrap.js"
DELIVERY_GATE_JS = ROOT / "app" / "static" / "game" / "delivery-gate.js"
BUILD_GAME_JS = ROOT / "app" / "static" / "build-game.js"


def test_delivery_gate_is_post_core_and_does_not_block_static_entry():
    html = GAME_HTML.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP_JS.read_text(encoding="utf-8")

    assert "/assets/build-game.js" in html
    assert "/assets/game/game-bootstrap.js" in html
    assert "/assets/game/delivery-gate.js" not in html
    assert "game/delivery-gate.js" in bootstrap
    assert "game/action-runtime.js" not in bootstrap
    assert bootstrap.index("await withTimeout(window.loadBuildGame()") < bootstrap.index("startEnhancements();")


def test_completed_execution_requires_independent_verifier_task():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")
    build = BUILD_GAME_JS.read_text(encoding="utf-8")

    assert "[DEVPILOT_DELIVERY_VERIFIER_V1]" in script
    assert "MAX_PHASES = 7" in script
    assert "TASK_LIMIT = 24" in script
    assert "normalize(latest.status) !== 'completed'" in script
    assert "Gate ${phaseId} · Verificar entrega real" in script
    assert "requires_approval: false" in script
    assert "Não aceite o status completed" in script
    assert "isVerifierTask(task)" in build
    assert "isPassed = task" in build


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


def test_failed_verifier_can_be_retried_without_advancing_phase():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")

    assert "retryFailed = false" in script
    assert "retryFailed && FAILED.has(taskStatus)" in script
    assert "!isVerifier(task) && normalize(task.status) === 'completed'" in script
    assert "return createVerifier" in script


def test_delivery_gate_does_not_wrap_main_loader():
    script = DELIVERY_GATE_JS.read_text(encoding="utf-8")

    assert "window.loadBuildGame = async" not in script
    assert "const originalLoad = window.loadBuildGame" not in script
    assert "__devpilotDeliveryGateDoesNotWrapLoader = true" in script
    assert "devpilot:game:rendered" in script
