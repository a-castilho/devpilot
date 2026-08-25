from pathlib import Path

from app.main import STATIC, spa


FEATURE_LOADER = Path(STATIC / "feature-loader.js")


def test_mission_control_assets_exist():
    assert (STATIC / "mission-control.js").is_file()
    assert (STATIC / "mission-control.css").is_file()


def test_regular_spa_route_does_not_auto_load_mission_control_runtime():
    response = spa("reports")
    rendered = response.body.decode("utf-8")

    assert "/assets/mission-control.js?v=" not in rendered
    assert "/assets/feature-loader.js?v=" in rendered


def test_mission_control_is_available_only_through_explicit_admin_bundle():
    loader = FEATURE_LOADER.read_text(encoding="utf-8")

    assert "admin: [" in loader
    assert "'mission-control.js'" in loader
    admin_block = loader.split("admin: [", 1)[1].split("],", 1)[0]
    assert "'mission-control.js'" in admin_block


def test_mission_control_keeps_professional_mode_available():
    script = Path(STATIC / "mission-control.js").read_text(encoding="utf-8")

    assert "MODE_MISSION = 'mission'" in script
    assert "MODE_PROFESSIONAL = 'professional'" in script
    assert "devpilot-workspace-mode" in script
    assert "Modo profissional" in script
