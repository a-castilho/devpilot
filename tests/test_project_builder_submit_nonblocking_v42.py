from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVISIONING = (ROOT / "app/static/project-provisioning.js").read_text(encoding="utf-8")


def test_builder_success_does_not_wait_full_dashboard_reload():
    block = PROVISIONING.split("async function createAutomaticProject()", 1)[1].split(
        "form.addEventListener('submit'", 1
    )[0]

    assert "await load();" not in block
    assert "showView('projects')" in block
    assert "void loadProjects();" in block
    assert "void loadDashboard();" in block


def test_builder_success_does_not_reapply_heavy_preset_before_navigation():
    block = PROVISIONING.split("async function createAutomaticProject()", 1)[1].split(
        "form.addEventListener('submit'", 1
    )[0]

    assert "data-builder-preset" not in block
    assert block.index("showView('projects')") < block.index("form.reset()")
