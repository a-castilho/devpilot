from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_mobile_projects_runtime_does_not_own_new_project_navigation():
    assert "[data-project-builder-open]" not in MOBILE
    assert "openBuilderLowPower" not in MOBILE
    assert "BUILDER_OPEN_FLAG" not in MOBILE


def test_mobile_projects_runtime_keeps_low_power_guards_and_visuals():
    assert "__devpilotProjectsMemoryGuard" in MOBILE
    assert "__devpilotProjectsLoadGuard" in MOBILE
    assert "project-lite-ship-hangar" in MOBILE
    assert "data-project-game" in MOBILE
    assert "Mobile Projects Runtime V33 ativo" in MOBILE
