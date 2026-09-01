from pathlib import Path


SCRIPT = Path("app/static/mobile-project-card-compact.js")


def source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_projects_render_in_small_batches_on_low_power_devices():
    text = source()
    assert "lowPower() ? 6 : 15" in text
    assert "fullProjects.slice(0, Math.max(1, renderLimit))" in text
    assert "state.projects = visibleProjects" in text
    assert "state.projects = fullProjects" in text
    assert "data-projects-load-more" in text


def test_low_power_projects_skip_expensive_ship_dom():
    text = source()
    assert "card.dataset.shipEnhanced = '1'" in text
    assert "project-ship-svg" in text
    assert "project-ship-hangar" in text
    assert "animation: none !important" in text
    assert "filter: none !important" in text


def test_projects_guard_uses_browser_render_containment_without_observer_loop():
    text = source()
    assert "content-visibility: auto" in text
    assert "contain-intrinsic-size" in text
    assert "MutationObserver" not in text
