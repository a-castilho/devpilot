from pathlib import Path

from app.main import STATIC, spa


def test_mission_control_assets_exist():
    assert (STATIC / "mission-control.js").is_file()
    assert (STATIC / "mission-control.css").is_file()


def test_regular_spa_route_loads_mission_control_runtime():
    response = spa("reports")
    rendered = response.body.decode("utf-8")

    assert "/assets/mission-control.js?v=" in rendered


def test_mission_control_keeps_professional_mode_available():
    script = Path(STATIC / "mission-control.js").read_text(encoding="utf-8")

    assert "MODE_MISSION = 'mission'" in script
    assert "MODE_PROFESSIONAL = 'professional'" in script
    assert "devpilot-workspace-mode" in script
    assert "Modo profissional" in script
