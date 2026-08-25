from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_persisted_session_requires_explicit_resume():
    auth = read("app/static/auth-ui.js")

    assert "Continuar sessão" in auth
    assert "dashboard só será iniciado depois da sua confirmação" in auth
    assert "window.__devpilotAuthReady = new Promise" in auth
    assert "renderResumeSession(token)" in auth


def test_fresh_login_hands_off_without_page_reload():
    auth = read("app/static/auth-ui.js")
    login_block = auth.split("form?.addEventListener('submit'", 1)[1].split("function renderResumeSession", 1)[0]

    assert "localStorage.setItem(TOKEN_KEY, data.access_token)" in login_block
    assert "handoffAuthenticatedRuntime(errorBox)" in login_block
    assert "devpilot:login-complete" in login_block
    assert "location.reload()" not in login_block
    assert "completeAuth(true)" in auth
    assert "sessionStorage.getItem" not in auth
    assert "sessionStorage.setItem" not in auth


def test_login_disables_backdrop_compositor_until_core_is_ready():
    auth = read("app/static/auth-ui.js")

    assert "devpilot-auth-pending" in auth
    assert "backdrop-filter: none !important" in auth
    assert "-webkit-backdrop-filter: none !important" in auth
    assert "visibility: hidden !important" in auth
    assert "document.addEventListener('devpilot:authenticated-core-ready', finish" in auth
    assert "revealDashboard()" in auth
    assert "devpilot:dashboard-revealed" in auth


def test_auth_does_not_override_document_query_selector():
    auth = read("app/static/auth-ui.js")

    assert "document.querySelector =" not in auth
    assert "nativeQuerySelector" not in auth


def test_core_app_uses_real_multi_selector_for_approval_buttons():
    app = read("app/static/app.js")

    assert "$$('.approve', table).forEach" in app
    assert "$('.approve').forEach" not in app


def test_core_app_has_no_legacy_save_token_click_binding():
    app = read("app/static/app.js")

    assert "$('#save-token').onclick" not in app
    assert "$('#token').value" not in app


def test_post_login_does_not_fetch_heavy_projects_or_organizations():
    app = read("app/static/app.js")
    dashboard = app.split("async function loadDashboard()", 1)[1].split("async function loadProjects()", 1)[0]

    assert "api('/overview')" in dashboard
    assert "api('/ui/tasks?limit=5')" in dashboard
    assert "api('/projects')" not in dashboard
    assert "api('/organizations')" not in dashboard
    assert "agents_md" not in dashboard
    assert "codex_config" not in dashboard


def test_large_project_and_task_text_is_excluded_from_summary_routes():
    routes = read("app/frontend_ui_routes.py")

    project_summary = routes.split('@router.get("/projects")', 1)[1].split('@router.get("/tasks")', 1)[0]
    task_summary = routes.split('@router.get("/tasks")', 1)[1].split('@router.get("/tasks/{task_id}")', 1)[0]

    assert "Project.agents_md" not in project_summary
    assert "Project.codex_config" not in project_summary
    assert "Task.prompt" not in task_summary
    assert '"prompt": item.prompt' in routes


def test_mobile_navigation_has_no_attribute_mutation_observer_loop():
    app = read("app/static/app.js")

    assert "new MutationObserver(sync).observe(nav" not in app
    assert "attributeFilter: ['class', 'hidden', 'style']" not in app
