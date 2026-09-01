from pathlib import Path

SOURCE = Path("app/static/mission-control-ai-dashboard.js").read_text(encoding="utf-8")


def test_mission_control_fleet_renders_real_ship_hangar():
    assert "mc-fleet-ship-hangar" in SOURCE
    assert "mc-fleet-ship-svg" in SOURCE
    assert "mc-fleet-ship-hud" in SOURCE


def test_mission_control_ship_has_operational_gauges():
    assert "ENERGIA" in SOURCE
    assert "ESCUDO" in SOURCE
    assert "PRONTO" in SOURCE


def test_professional_mode_is_not_targeted_by_ship_styles():
    assert "body.mission-control-mode .mc-fleet" in SOURCE
    assert "body.mission-control-mode .mc-ship-card.mc-ship-visual" in SOURCE


def test_fleet_is_redecorated_after_runtime_render():
    assert "MutationObserver" in SOURCE
    assert "enhanceFleetShips" in SOURCE
