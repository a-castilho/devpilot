from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_mission_control_fleet_navigation_v22_contract():
    source = (ROOT / "app/static/mission-control.js").read_text(encoding="utf-8")

    assert "const openProfessionalView = (view, projectId = '')" in source
    assert "setMode(MODE_PROFESSIONAL, true);" in source
    assert '.sidebar .nav[data-view="${view}"]' in source
    assert "nav.click();" in source
    assert "devpilot:fleet-opened" in source
    assert "window.devpilotOpenTaskModal" in source
    assert "openProfessionalView('projects')" in source
    assert "openProfessionalView('tasks')" in source


if __name__ == "__main__":
    test_mission_control_fleet_navigation_v22_contract()
    print("MISSION CONTROL FLEET V22: contrato OK")
