from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / "app/project_provisioning_routes.py").read_text(encoding="utf-8")
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")


def test_automatic_registration_is_not_blocked_by_github_configuration():
    provision = ROUTES.split('def provision_project(', 1)[1]
    fallback = provision.split('item = Project(', 1)[0]

    assert 'return persist_deferred_project(' in fallback
    assert 'if principal.role is Role.SUPER_ADMIN' not in fallback
    assert 'repository_pending' in ROUTES
    assert 'source="automatic_provision_fallback"' in fallback


def test_builder_does_not_require_cached_castilho_organization_before_submit():
    submit = BUILDER.split("form.addEventListener('submit'", 1)[1]

    assert "if (!castilhoOrganization())" not in submit
    assert "const project = await api('/projects/provision'" in submit
    assert 'repositoryPending' in submit
    assert 'GitHub pendente' in submit


def test_regular_builder_defaults_to_automatic_git_and_success_does_not_wait_dashboard_reload():
    open_builder = BUILDER.split('function openBuilder()', 1)[1].split("document.querySelectorAll('[data-project-builder-open]')", 1)[0]
    submit = BUILDER.split("form.addEventListener('submit'", 1)[1]

    assert 'createRadio.disabled = false' in open_builder
    assert 'createRadio.checked = true' in open_builder
    assert 'connectRadio.checked = false' in open_builder
    assert "showView('projects');" in submit
    assert 'await load();' not in submit
