from __future__ import annotations

from pathlib import Path

from app.services.github_workflows import repository_full_name


ROOT = Path(__file__).resolve().parents[1]


def test_repository_full_name_accepts_https_and_ssh():
    assert repository_full_name("https://github.com/a-castilho/devpilot.git") == "a-castilho/devpilot"
    assert repository_full_name("git@github.com:a-castilho/devpilot.git") == "a-castilho/devpilot"


def test_workflow_service_correlates_only_exact_persisted_commit():
    source = (ROOT / "app/services/github_workflows.py").read_text()

    assert 'params={"head_sha": sha, "per_page": 20}' in source
    assert 'str(item.get("head_sha") or "") == sha' in source
    assert '"reason": "workflow_not_found_for_commit"' in source
    assert "/actions/runs/{run_id}/jobs" in source


def test_deployment_service_correlates_only_exact_persisted_commit():
    source = (ROOT / "app/services/github_workflows.py").read_text()

    assert 'f"https://api.github.com/repos/{full_name}/deployments"' in source
    assert 'params={"sha": sha, "per_page": 20}' in source
    assert 'str(item.get("sha") or "") == sha' in source
    assert '"reason": "deployment_not_found_for_commit"' in source
    assert "/deployments/{deployment_id}/statuses" in source
    assert '"verified": False' in source
    assert '"reason": "http_health_not_probed"' in source


def test_task_workflow_route_uses_latest_run_and_project_credential():
    source = (ROOT / "app/workflow_observability_routes.py").read_text()

    assert '@router.get("/tasks/{task_id}/workflow-evidence")' in source
    assert '@router.get("/tasks/{task_id}/deployment-evidence")' in source
    assert "Run.started_at.desc(), Run.attempt.desc()" in source
    assert "run.commit_sha" in source
    assert "Vault().decrypt" in source
    assert "fetch_workflow_evidence" in source
    assert "fetch_deployment_evidence" in source


def test_workflow_route_is_registered():
    main = (ROOT / "app/main.py").read_text()

    assert "workflow_observability_router" in main
    assert "app.include_router(workflow_observability_router)" in main


def test_task_ui_renders_real_workflow_and_jobs_without_inference():
    source = (ROOT / "app/static/task-workflow-observability.js").read_text()

    assert "/workflow-evidence" in source
    assert "workflow.conclusion || workflow.status || 'unknown'" in source
    assert "evidence.jobs" in source
    assert "Não correlacionado" in source
    assert "Deploy / Health" in source
