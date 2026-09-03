from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "app/static/project-builder-mobile-runtime-v39.js").read_text(encoding="utf-8")
SHIPS = (ROOT / "app/static/mobile-game-ships-stable.js").read_text(encoding="utf-8")
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/page-navigation-v26.css").read_text(encoding="utf-8")


def test_legacy_mobile_builder_runtime_remains_inert_history() -> None:
    assert "Project Builder Mobile V39 virtualizado" in RUNTIME
    assert "project-builder-mobile-runtime-v39.js" not in SHIPS
    assert "ensureBuilderRuntime" not in SHIPS


def test_mobile_ship_runtime_is_confined_to_projects_domain() -> None:
    assert "__devpilotMobileGameShipsStableV94" in SHIPS
    assert "projectsObserver.observe(host, {childList:true, subtree:true})" in SHIPS
    assert "if (!isMobile() || !projectsViewActive()) return" in SHIPS
    assert "project-builder-groups" not in SHIPS
    assert "document.createElement('script')" not in SHIPS


def test_builder_performance_is_owned_by_canonical_runtime() -> None:
    assert "__devpilotProjectBuilderV94" in BUILDER
    assert "requestAnimationFrame(updateSummary)" in BUILDER
    assert "#new-project-view .builder-group" in CSS
    assert "content-visibility: auto" in CSS


def test_game_runtime_does_not_observe_entire_document() -> None:
    assert "observer.observe(document.documentElement" not in SHIPS
    assert "projectsObserver.observe(host, {childList:true, subtree:true})" in SHIPS
