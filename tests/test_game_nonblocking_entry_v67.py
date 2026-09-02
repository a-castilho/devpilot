from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "app/static/game/index.html").read_text(encoding="utf-8")
BUILD = (ROOT / "app/static/build-game.js").read_text(encoding="utf-8")
BOOT = (ROOT / "app/static/game/game-bootstrap.js").read_text(encoding="utf-8")


def test_v73_removes_v67_loader_bridge():
    assert "data-game-nonblocking-entry-v67" not in INDEX
    assert "__devpilotGameNonBlockingEntryV67" not in INDEX
    assert "window.loadBuildGame = (...args) =>" not in INDEX


def test_static_document_has_visible_boot_shell_before_network():
    shell = INDEX.index('data-game-boot-state="loading"')
    engine = INDEX.index('/assets/build-game.js')
    assert shell < engine
    assert 'id="build-game-view"' in INDEX


def test_bootstrap_uses_single_real_load_with_timeout():
    assert "await withTimeout(window.loadBuildGame()" in BOOT
    assert "window.__devpilotGameCoreReady = true" in BOOT
    assert "startEnhancements();" in BOOT


def test_real_engine_hydrates_projects_and_history():
    assert "await ensureProjects();" in BUILD
    assert "await api(`/tasks?project_id=${encodeURIComponent(selectedProjectId)}&limit=500`)" in BUILD
    assert "document.dispatchEvent(new CustomEvent('devpilot:game:rendered'" in BUILD


def test_v73_has_boot_retry_without_recursive_bridge_polling():
    assert 'id="game-error-retry"' in BOOT
    assert "void boot()" in BOOT
    assert "while (" not in BOOT
    assert "MutationObserver" not in BOOT
