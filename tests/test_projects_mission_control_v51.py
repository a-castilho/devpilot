from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"


def source() -> str:
    return (STATIC / "mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_projects_are_presented_as_mission_control():
    js = source()
    assert "Mission Control" in js
    assert "Frota de projetos" in js
    assert "MISSION_VERSION = 'mission-control-v51'" in js
    assert "project-mission-control" in js
    assert "mission-control-hud" in js


def test_mobile_ship_skin_is_static_and_low_power():
    js = source()
    assert "mission-ship-lite" in js
    assert "project-ship-svg" in js
    assert "display:none!important" in js
    assert "animation:none!important" in js
    assert "filter:none!important" in js
    assert "clip-path:polygon" in js


def test_project_ship_has_class_state_and_telemetry():
    js = source()
    for skin in ("DEFENSE", "LAB", "CARGO", "SCOUT", "COMMAND"):
        assert skin in js
    assert "missionState(project)" in js
    assert "projectTelemetry(project" in js
    assert "ENERGIA" in js
    assert "ESCUDO" in js
    assert "INTEGR." in js


def test_play_button_opens_selected_project_in_game():
    js = source()
    assert "data-mission-play" in js
    assert "GAME_PROJECT_KEY = 'devpilot-build-game-project'" in js
    assert "localStorage.setItem(GAME_PROJECT_KEY, projectId)" in js
    assert "localStorage.removeItem(GAME_MISSION_KEY)" in js
    assert "window.location.assign('/game/index.html?v=51')" in js


def test_memory_guard_keeps_small_initial_batch():
    js = source()
    assert "const batchSize = () => lowPower() ? 6 : 15" in js
    assert "const LOAD_TIMEOUT_MS = 7000" in js
    assert "observer.observe(target, {childList:true})" in js
    assert "subtree:true" not in js
