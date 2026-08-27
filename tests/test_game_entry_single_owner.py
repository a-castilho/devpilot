from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY_JS = ROOT / "app" / "static" / "game-entry.js"
SHELL_JS = ROOT / "app" / "static" / "game-shell.js"


def test_game_entry_does_not_mount_shell_directly():
    entry = ENTRY_JS.read_text(encoding="utf-8")
    assert "target.click();" in entry
    assert "DevPilotGameShell?.enter" not in entry


def test_game_shell_owns_navigation_mount_and_base_load():
    shell = SHELL_JS.read_text(encoding="utf-8")
    assert '.sidebar nav .nav[data-view="build-game"]' in shell
    assert "void openBaseGameFromNavigation(nav);" in shell
    assert "showView('build-game');" in shell
    assert "if (view) enterGame(view);" in shell
    assert "await runBaseLoad();" in shell
