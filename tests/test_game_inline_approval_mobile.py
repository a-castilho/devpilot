from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
INDEX = (STATIC / "game" / "index.html").read_text(encoding="utf-8")
SCRIPT = (STATIC / "game" / "inline-approval.js").read_text(encoding="utf-8")


def test_standalone_game_loads_inline_approval_before_bootstrap():
    approval = '/assets/game/inline-approval.js?v=game-v46-20260901'
    bootstrap = '/assets/game/game-bootstrap.js?v=game-v46-20260901'
    assert approval in INDEX
    assert bootstrap in INDEX
    assert INDEX.index(approval) < INDEX.index(bootstrap)


def test_mobile_game_assets_have_new_cache_revision():
    assert 'frontend-v31' not in INDEX
    assert INDEX.count('game-v46-20260901') >= 8


def test_awaiting_approval_is_resolved_inside_game():
    assert "normalize(task?.status) === 'awaiting_approval'" in SCRIPT
    assert "data.gameInlineApprove" not in SCRIPT
    assert "approve.dataset.gameInlineApprove" in SCRIPT
    assert "Aprovar fase" in SCRIPT
    assert "/approve`" in SCRIPT
    assert "method:'POST'" in SCRIPT
    assert "A missão continua sem sair do jogo" in SCRIPT
    assert "window.location.assign('/')" not in SCRIPT


def test_game_caps_large_task_query_for_low_memory_runtime():
    assert "limit=500" in SCRIPT
    assert "limit=120" in SCRIPT
    assert "gameLowMemoryApi" in SCRIPT
