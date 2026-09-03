from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / "app/project_provisioning_routes.py").read_text(encoding="utf-8")
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")


def test_registration_persists_before_external_github_io():
    provision = ROUTES.split('def provision_project(', 1)[1]

    assert 'background_tasks: BackgroundTasks' in provision
    assert 'item = persist_deferred_project(' in provision
    assert 'source="automatic_provision_queued"' in provision
    assert 'background_tasks.add_task(' in provision
    assert 'provision_repository_in_background' in provision
    assert 'create_github_repository(' not in provision


def test_github_provisioning_is_owned_by_background_worker_path():
    background = ROUTES.split('def provision_repository_in_background(', 1)[1].split(
        '@router.post("/projects/deferred"', 1
    )[0]

    assert 'with SessionLocal() as db:' in background
    assert 'create_github_repository(' in background
    assert 'repository_provision_state"] = "failed"' in background
    assert 'repository_provision_state"] = "ready"' in background
    assert 'db.commit()' in background


def test_builder_does_not_require_cached_castilho_organization_before_submit():
    submit = BUILDER.split("form.addEventListener('submit'", 1)[1]

    assert "if (!castilhoOrganization())" not in submit
    assert "const project = await api('/projects/provision'" in submit
    assert 'repositoryPending' in submit
    assert 'GitHub pendente' in submit


def test_regular_builder_defaults_to_automatic_git_and_success_does_not_wait_dashboard_reload():
    open_builder = BUILDER.split('function openBuilder()', 1)[1].split(
        "document.querySelectorAll('[data-project-builder-open]')", 1
    )[0]
    submit = BUILDER.split("form.addEventListener('submit'", 1)[1]

    assert 'createRadio.disabled = false' in open_builder
    assert 'createRadio.checked = true' in open_builder
    assert 'connectRadio.checked = false' in open_builder
    assert "showView('projects');" in submit
    assert 'await load();' not in submit
