from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def test_viewport_loader_uses_single_execution_submit_runtime():
    source = (STATIC / "viewport-adaptive-v15.js").read_text(encoding="utf-8")
    assert "executions-submit-v29.js" in source
    assert "executions-submit-v27.js" not in source
    assert "script.async = false" in source


def test_execution_labels_are_consolidated():
    source = (STATIC / "executions-v18.js").read_text(encoding="utf-8")
    assert "Execuções por status" in source
    assert "Origem das execuções" in source
    assert "Esta execução" in source
    assert "Salvar execução" in source
    assert "devpilot:execution-created" in source


def test_game_runtime_never_exposes_raw_fetch_failure():
    source = (STATIC / "game" / "runtime.js").read_text(encoding="utf-8")
    assert "networkErrorMessage" in source
    assert "Não foi possível conectar ao DevPilot" in source
    assert "AbortController" in source
    assert "method === 'GET' && attempt === 0" in source


def test_game_bootstrap_uses_shared_api_runtime():
    source = (STATIC / "game" / "game-bootstrap.js").read_text(encoding="utf-8")
    assert "window.api('/auth/me')" in source
    assert "fetch('/api/auth/me'" not in source
    assert "game-error-retry" in source


def test_game_assets_are_cache_busted():
    source = (STATIC / "game" / "index.html").read_text(encoding="utf-8")
    assert "/assets/game/runtime.js?v=frontend-v30" in source
    assert "/assets/build-game.js?v=frontend-v30" in source
    assert "/assets/game/game-bootstrap.js?v=frontend-v30" in source
