from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "app/static/project-builder.js").read_text(encoding="utf-8")
LOADER = (ROOT / "app/static/feature-loader.js").read_text(encoding="utf-8")


def test_simple_builder_is_the_only_owner_of_project_registration():
    bundle = LOADER.split("projectBuilder:", 1)[1].split("projects:", 1)[0]

    assert "'project-builder.js'" in bundle
    assert "project-provisioning.js" not in bundle
    assert "project-description-profile.js" not in bundle
    assert "requestIdleCallback" not in LOADER
    assert "form?.dataset.simpleBuilderReady === '1'" in LOADER


def test_simple_builder_supports_deferred_or_existing_repository():
    assert "const form = originalForm.cloneNode(false)" in BUILDER
    assert "originalForm.replaceWith(form)" in BUILDER
    assert "Repositório GitHub <small>(opcional)</small>" in BUILDER
    assert "repositoryUrl ? '/projects' : '/projects/provision'" in BUILDER
    assert "Somente o Super Admin pode conectar um repositório existente." in BUILDER


def test_success_returns_to_projects_before_background_refresh():
    success = BUILDER.split("const project = await request(endpoint", 1)[1]

    assert "state.projects.unshift(project)" in success
    assert success.index("goProjects();") < success.index("void Promise.resolve(window.loadProjects())")
