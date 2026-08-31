from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NAV = ROOT / "app/static/page-navigation-v26.js"
INDEX = ROOT / "app/static/index.html"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_navigation_v38_is_single_internal_route_authority():
    js = source(NAV)
    assert "__devpilotPageNavigationV38" in js
    assert "const NAV_SELECTOR = '[data-view]'" in js
    assert "window.devpilotNavigate = navigate" in js
    assert "targetFor(viewName)" in js
    assert "markOnlyView(viewName)" in js


def test_navigation_v38_covers_dashboard_and_mobile_data_view_links():
    js = source(NAV)
    html = source(INDEX)
    assert 'data-view="projects">Ver projetos' in html
    assert 'class="quick-action" data-view="projects"' in html
    assert 'class="quick-action" data-view="tasks"' in html
    assert "event.target" in js
    assert "closest?.(NAV_SELECTOR)" in js
    assert "source: item.closest('.sidebar')" in js


def test_navigation_v38_supports_direct_hash_routes_and_history():
    js = source(NAV)
    assert "location.hash.match(/^#\\/([^/?#]+)/)" in js
    assert "location.hash.match(/^#([A-Za-z0-9_-]+)$/)" in js
    assert "window.addEventListener('popstate'" in js
    assert "window.addEventListener('hashchange'" in js
    assert "navigateFromLocation('history')" in js
    assert "navigateFromLocation('hash')" in js


def test_navigation_v38_does_not_claim_missing_dynamic_views():
    js = source(NAV)
    assert "if (!target)" in js
    assert "emitNavigationFailure(viewName" in js
    assert "'view-not-found'" in js


def test_navigation_v38_has_titles_for_core_and_admin_views():
    js = source(NAV)
    for token in (
        "projects: 'Projetos'",
        "tasks: 'Execuções'",
        "'cloud-admin': 'Clouds'",
        "'deploy-admin': 'Deploy'",
        "'mission-control': 'Mission Control'",
        "'rag-admin': 'RAG Admin'",
    ):
        assert token in js


def test_navigation_v38_updates_visibility_accessibility_and_url_together():
    js = source(NAV)
    assert "view.hidden = !active" in js
    assert "view.setAttribute('aria-hidden'" in js
    assert "aria-current" in js
    assert "updateHistory(viewName" in js
    assert "root.dataset.devpilotView = viewName" in js
    assert "devpilot:view-changed" in js
    assert "devpilot:page-ready" in js
