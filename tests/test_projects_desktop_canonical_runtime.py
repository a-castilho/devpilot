from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")
PROJECTS_CSS = (ROOT / "app/static/layout-projects-v6.css").read_text(encoding="utf-8")


def test_desktop_does_not_fall_back_to_legacy_projects_ui_by_hardware_only():
    assert "const compactViewport = () => window.matchMedia?.('(max-width: 900px)')?.matches === true;" in LOADER
    assert "const lowPowerDevice = compactViewport() && constrainedHardware;" in LOADER
    assert "const constrainedProjectsRuntime = () => compactViewport();" in LOADER
    assert "lowPowerDevice ||\n    window.matchMedia?.('(max-width: 900px)')" not in LOADER


def test_desktop_projects_bundle_keeps_current_ship_interface():
    projects_start = LOADER.index("projects: [")
    projects_end = LOADER.index("taskModal:", projects_start)
    bundle = LOADER[projects_start:projects_end]

    assert "'project-ships.js'" in bundle
    assert "'product-delivery-ui.js'" in bundle
    assert "project-ship-hangar" in PROJECTS_CSS
    assert "project-ship-svg" in PROJECTS_CSS


def test_reduced_motion_is_not_used_as_a_version_selector():
    assert "classList.toggle('devpilot-reduced-motion', reducedMotion)" in LOADER
    assert "const lowPowerDevice =\n    reducedMotion ||" not in LOADER
