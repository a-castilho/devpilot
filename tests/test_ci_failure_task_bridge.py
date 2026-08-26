from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ci_failure_workflow_reacts_only_to_failed_ci_runs():
    workflow = read(".github/workflows/ci-failure-task.yml")

    assert 'workflows: ["CI"]' in workflow
    assert "workflow_run.conclusion == 'failure'" in workflow
    assert "scripts/ci-failure-to-task.py" in workflow
    assert "DEVPILOT_AUTOMATION_TOKEN" in workflow
    assert "DEVPILOT_AUTOMATION_URL" in workflow


def test_ci_failure_bridge_is_idempotent_and_uses_real_task_api():
    bridge = read("scripts/ci-failure-to-task.py")

    assert "[github-ci-run:{run_id}]" in bridge
    assert '"GET", "/api/projects"' in bridge
    assert '"GET", f"/api/tasks?{query}"' in bridge
    assert '"POST", "/api/tasks", payload' in bridge
    assert '"source": "api"' in bridge
    assert '"requires_approval": False' in bridge


def test_ci_failure_bridge_never_bypasses_sensitive_action_policy():
    bridge = read("scripts/ci-failure-to-task.py")

    assert "Não publique alterações" in bridge
    assert "não integre a branch main automaticamente" in bridge
    assert "bash scripts/test-all.sh" in bridge
    assert "Authorization" in bridge
    assert "DEVPILOT_AUTOMATION_TOKEN" in bridge
