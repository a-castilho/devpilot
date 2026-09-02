from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "app/static/game/game-bootstrap.js"
INDEX = ROOT / "app/static/game/index.html"
UX = ROOT / "app/static/game/project-switch-approval.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v78_boots_project_switch_and_approval_addon():
    boot = text(BOOT)
    index = text(INDEX)
    assert "game/project-switch-approval.js" in boot
    assert "game-flow-v78-20260902" in boot
    assert "server-orchestrated-v78" in boot
    assert "game-flow-v78-20260902" in index
    assert 'data-devpilot-game-version="v78"' in index


def test_active_round_can_switch_project_without_stopping_server_round():
    source = text(UX)
    assert "data-game78-project-switch" in source
    assert "localStorage.setItem(PROJECT_KEY, target)" in source
    assert "localStorage.removeItem(MISSION_KEY)" in source
    assert "window.location.reload()" in source
    assert "A rodada atual continua no servidor" in source


def test_awaiting_approval_is_actionable_inside_game():
    source = text(UX)
    assert "awaiting_approval" in source
    assert "Aprovar e continuar" in source
    assert "`/tasks/${encodeURIComponent(state.taskId)}/approve`" in source
    assert "method:'POST'" in source
    assert "await window.loadBuildGame()" in source
