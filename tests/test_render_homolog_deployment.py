from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_waits_for_ci_before_auto_deploy():
    blueprint = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "name: devpilot-homolog" in blueprint
    assert "renderSubdomainPolicy: enabled" in blueprint
    assert "autoDeployTrigger: checksPass" in blueprint
    assert "healthCheckPath: /health" in blueprint


def test_homolog_workflow_fails_fast_for_unprovisioned_render_target():
    workflow = (ROOT / ".github/workflows/deploy-homolog.yml").read_text(encoding="utf-8")

    assert "vars.RENDER_HOMOLOG_BASE_URL" in workflow
    assert "Verify Render service is provisioned" in workflow
    assert 'if [ "$code" = "404" ]; then' in workflow
    assert "service/Blueprint is not provisioned" in workflow
    assert "relying on Render autoDeployTrigger=commit" not in workflow
