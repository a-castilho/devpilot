import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pr_auto_repair.py"
WORKFLOW = ROOT / ".github" / "workflows" / "pr-auto-repair.yml"
POLICY = ROOT / ".devpilot" / "pr-auto-repair.json"


def _module():
    spec = importlib.util.spec_from_file_location("devpilot_pr_auto_repair", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pr_auto_repair_policy_is_scoped_and_never_merges():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["enabled"] is True
    assert policy["allow_branch_push"] is True
    assert policy["allow_merge"] is False
    assert policy["max_attempts"] == 3
    assert policy["require_open_pull_request"] is True
    assert policy["require_same_repository"] is True
    assert policy["require_full_validation"] is True


def test_pr_auto_repair_workflow_only_reacts_to_failed_ci_and_has_no_merge_permission():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "conclusion == 'failure'" in text
    assert "conclusion == 'timed_out'" in text
    assert "head_repository.full_name == github.repository" in text
    assert "pull-requests: read" in text
    assert "contents: write" in text
    assert "actions: write" in text
    assert "pull-requests: write" not in text
    assert "merge_pull_request" not in text
    assert "gh pr merge" not in text


def test_safety_guard_blocks_policy_gates_and_secrets():
    module = _module()
    errors = module.safety_errors(
        ["app/example.py", ".github/workflows/ci.yml"],
        "+TOKEN=github_pat_example012345678901234567890",
    )
    assert any("protected paths changed" in item for item in errors)
    assert any("possible secret" in item for item in errors)


def test_controller_has_hard_three_attempt_circuit_breaker_and_no_force_push():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "MAX_HARD_ATTEMPTS = 3" in text
    assert "fix(ci): auto-repair attempt " in text
    assert '"push", "origin"' in text
    assert "--force" not in text
    assert '"workflow", "run", "ci.yml"' in text
    assert 'DEVPILOT_RUN_BROWSER_E2E"] = "1"' in text
