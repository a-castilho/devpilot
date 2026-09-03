from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
MENU = (STATIC / "mobile-accordion-menu.js").read_text(encoding="utf-8")
BUILDER = (STATIC / "project-builder.js").read_text(encoding="utf-8")
CSS = (STATIC / "page-navigation-v26.css").read_text(encoding="utf-8")


def test_legacy_mobile_builder_runtime_is_removed() -> None:
    assert not (STATIC / "project-builder-mobile-runtime-v39.js").exists()
    assert not (STATIC / "mobile-game-ships-stable.js").exists()


def test_mobile_menu_does_not_inject_domain_runtimes() -> None:
    assert "__devpilotMobileAccordionMenuV94" in MENU
    assert "project-builder-mobile-runtime-v39.js" not in MENU
    assert "mobile-game-ships-stable.js" not in MENU
    assert "ensureGameShipsRuntime" not in MENU
    assert "document.createElement('script')" not in MENU


def test_builder_performance_is_owned_by_canonical_runtime() -> None:
    assert "__devpilotProjectBuilderV94" in BUILDER
    assert "requestAnimationFrame(updateSummary)" in BUILDER
    assert "#new-project-view .builder-group" in CSS
    assert "content-visibility: auto" in CSS


def test_mobile_menu_is_event_driven() -> None:
    assert "devpilot:view-changed" in MENU
    assert "devpilot:page-ready" in MENU
    assert "devpilot:feature-ready" in MENU
    assert "MutationObserver" not in MENU
