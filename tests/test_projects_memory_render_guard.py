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


def test_mobile_viewport_is_always_treated_as_low_power_for_projects():
    text = source()
    assert "matchMedia?.('(max-width: 900px)')" in text
    assert "classList.contains('devpilot-low-power') || mobileViewport()" in text
    assert "fetchLimit = () => lowPower() ? 12 : 50" in text


def test_low_power_project_loader_bounds_network_payload_and_timeout():
    text = source()
    assert "__devpilotProjectsLoadGuard" in text
    assert "api(`/ui/projects?limit=${fetchLimit()}`)" in text
    assert "Promise.race([request, timeout])" in text
    assert "12000" in text
    assert "loadProjects = guardedLoadProjects" in text


def test_low_power_projects_skip_expensive_ship_dom():
    text = source()
    assert "card.dataset.shipEnhanced = '1'" in text
    assert "project-ship-svg" in text
    assert "project-ship-hangar" in text
    assert "animation: none !important" in text
    assert "filter: none !important" in text


def test_mobile_css_disables_ship_visuals_even_without_device_memory_api():
    text = source()
    mobile = text.split("@media (max-width: 900px)", 1)[1]
    assert "#projects-view .project-visual-overview" in mobile
    assert "#projects-view .project-ship-svg" in mobile
    assert "#projects-view .project-ship-hangar" in mobile
    assert "display: none !important" in mobile


def test_projects_guard_uses_browser_render_containment_without_observer_loop():
    text = source()
    assert "content-visibility: auto" in text
    assert "contain-intrinsic-size" in text
    assert "MutationObserver" not in text
