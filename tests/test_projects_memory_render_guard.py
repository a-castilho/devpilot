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


def test_mobile_is_always_treated_as_low_power_for_projects():
    text = source()
    assert "'(max-width: 900px)'" in text
    assert "if (mobileViewport()) document.documentElement.classList.add('devpilot-low-power')" in text
    assert "@media (max-width: 900px)" in text
    assert "#projects-view .project-visual-overview" in text


def test_low_power_projects_skip_expensive_ship_dom():
    text = source()
    assert "card.dataset.shipEnhanced = '1'" in text
    assert "project-ship-svg" in text
    assert "project-ship-hangar" in text
    assert "animation: none !important" in text
    assert "filter: none !important" in text


def test_projects_use_small_fast_api_page_with_timeout():
    text = source()
    assert "const LOAD_TIMEOUT_MS = 7000" in text
    assert "requestProjectPage" in text
    assert "`/ui/projects?limit=${safeLimit}`" in text
    assert "new AbortController()" in text
    assert "controller.abort()" in text
    assert "Projetos demoraram mais de 7 segundos" in text
    assert "window.loadProjects = fast" in text
    assert "loadProjects = fast" in text


def test_load_more_fetches_progressively_instead_of_materializing_fifty():
    text = source()
    assert "const MAX_PROJECTS = 50" in text
    assert "nextFetchLimit" in text
    assert "fetchedLimit + batchSize()" in text
    assert "await requestProjectPage(nextFetchLimit, desiredVisible)" in text


def test_projects_guard_uses_browser_render_containment_without_observer_loop():
    text = source()
    assert "content-visibility: auto" in text
    assert "contain-intrinsic-size" in text
    assert "MutationObserver" not in text
