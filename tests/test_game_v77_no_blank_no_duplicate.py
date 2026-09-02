from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")
GUARD = (ROOT / "app/static/game/task-payload-guard.js").read_text(encoding="utf-8")


def test_game_document_has_visible_fallback_before_javascript_runs():
    assert 'data-game-critical-boot-v77' in INDEX
    assert 'data-game-boot-state="loading"' in INDEX
    assert 'Preparando Modo Jogo' in INDEX
    assert '#build-game-view{display:block!important;visibility:visible!important;opacity:1!important' in INDEX
    assert 'game-flow-v77-20260902' in INDEX
    assert "const ASSET_REVISION = 'game-flow-v77-20260902'" in BOOT
    assert 'Não foi possível iniciar o jogo.' in BOOT


def test_game_guard_dedupes_sequential_posts_until_created_task_is_visible():
    assert 'const recentCreations = new Map();' in GUARD
    assert 'const RECENT_CREATION_TTL_MS = 60000;' in GUARD
    assert 'const recent = recentCreations.get(identity.key);' in GUARD
    assert "source:'recent'" in GUARD
    assert 'return recent.result;' in GUARD
    assert 'remember(identity, result)' in GUARD
    assert 'observeTasks(result);' in GUARD
    assert "requestPath.startsWith('/tasks?')" in GUARD
    assert "requestPath.startsWith('/ui/game-tasks?')" in GUARD
    assert 'window.__devpilotGameCreateSequentialDedup = true;' in GUARD


def test_visible_task_releases_recent_dedupe_by_exact_created_id_for_real_retry():
    assert "if (entry.taskId) return String(task?.id || '') === entry.taskId;" in GUARD
    assert 'recentCreations.delete(key);' in GUARD
    assert "trace('game-create:visible'" in GUARD
    assert "const FAILED = new Set(['failed', 'cancelled', 'canceled', 'archived']);" in GUARD
