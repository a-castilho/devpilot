from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_PROJECTS = (ROOT / "app/static/mobile-project-card-compact.js").read_text(encoding="utf-8")


def test_desktop_project_cards_force_ship_runtime_even_when_light_bundle_was_selected():
    assert "const SHIPS_SCRIPT = 'project-ships.js';" in MOBILE_PROJECTS
    assert "function ensureProjectShips()" in MOBILE_PROJECTS
    assert "window.__devpilotAssetRevisions?.[SHIPS_SCRIPT]" in MOBILE_PROJECTS
    assert "data.devpilotProjectShipsFallback" not in MOBILE_PROJECTS
    assert "devpilotProjectShipsFallback" in MOBILE_PROJECTS
    assert "document.body.appendChild(script);" in MOBILE_PROJECTS


def test_light_project_mode_is_restricted_to_phone_sized_viewports():
    assert "const mobileViewport = () => window.matchMedia?.('(max-width: 640px)')?.matches === true;" in MOBILE_PROJECTS
    assert "const desktopShipsViewport = () => window.matchMedia?.('(min-width: 641px)')?.matches === true;" in MOBILE_PROJECTS
    assert "const lowPower = () => mobileViewport();" in MOBILE_PROJECTS
    assert "@media (max-width: 640px)" in MOBILE_PROJECTS
    assert "@media (min-width: 641px)" in MOBILE_PROJECTS


def test_desktop_low_power_css_cannot_hide_ship_hangar():
    assert "html.devpilot-low-power #projects-view .project-ship-svg" in MOBILE_PROJECTS
    assert "display: block !important;" in MOBILE_PROJECTS
    assert "ensureProjectShips();" in MOBILE_PROJECTS
