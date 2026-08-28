import importlib.util
import json
import os
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


def test_workflow_only_reacts_to_failed_ci_and_has_no_merge_permission():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_run:" in text
    assert 'workflows: ["CI"]' in text
    assert "conclusion == 'failure'" in text
    assert "conclusion == 'timed_out'" in text
    assert "head_repository.full_name == github.repository" in text
    assert "pull-requests: read" in text
    assert "contents: write" in text
    assert "actions: write" in text
    assert "issues: write" in text
    assert "pull-requests: write" not in text
    assert "merge_pull_request" not in text
    assert "gh pr merge" not in text


def test_write_capable_workflow_uses_trusted_controller_and_no_persisted_credentials():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "persist-credentials: false" in text
    assert "Materialize trusted controller from main" in text
    assert "contents/scripts/pr_auto_repair.py?ref=main" in text
    assert "$RUNNER_TEMP/devpilot-pr-auto-repair-${GITHUB_RUN_ID}.py" in text
    assert text.count("GH_TOKEN: ${{ github.token }}") == 1
    assert text.count("DEVPILOT_GITHUB_TOKEN: ${{ github.token }}") == 1


def test_repair_workflow_prepares_same_validation_dependencies_as_ci():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python3 -m pip install -e '.[test,e2e]'" in text
    assert "python3 -m playwright install chromium" in text


def test_safety_guard_blocks_tests_gate_controls_and_secrets():
    module = _module()
    errors = module.safety_errors(
        ["app/example.py", "tests/test_example.py", ".github/workflows/ci.yml"],
        "+TOKEN=github_pat_example012345678901234567890",
    )
    assert any("protected paths changed" in item for item in errors)
    assert any("tests/test_example.py" in item for item in errors)
    assert any("possible secret" in item for item in errors)
    assert module.is_protected_repair_path("pyproject.toml") is True
    assert module.is_protected_repair_path("tests/conftest.py") is True
    assert module.is_protected_repair_path("app/service.py") is False


def test_untrusted_environment_drops_write_credentials_and_git_auth(monkeypatch):
    module = _module()
    for name in (
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "DEVPILOT_GITHUB_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "GITHUB_ENV",
        "GITHUB_OUTPUT",
        "GITHUB_PATH",
    ):
        monkeypatch.setenv(name, "should-not-leak")

    env = module.untrusted_env()

    for name in (
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "DEVPILOT_GITHUB_TOKEN",
        "ACTIONS_RUNTIME_TOKEN",
        "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        "GITHUB_ENV",
        "GITHUB_OUTPUT",
        "GITHUB_PATH",
    ):
        assert name not in env
    assert env["GIT_CONFIG_GLOBAL"] == os.devnull
    assert env["GIT_CONFIG_SYSTEM"] == os.devnull
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["SSH_AUTH_SOCK"] == ""
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert env["GIT_CONFIG_VALUE_0"] == ""


def test_controller_uses_durable_pr_attempt_counter_and_hard_cap():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "MAX_HARD_ATTEMPTS = 3" in text
    assert "durable_repair_count" in text
    assert "record_durable_attempt" in text
    assert "devpilot-auto-repair-attempt" in text
    assert 'f"repos/{repository}/issues/{pr_number}/comments"' in text
    assert "branch_repair_count()" in text


def test_controller_has_no_force_push_and_revalidates_full_ci():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "fix(ci): auto-repair attempt " in text
    assert '["git", "push", "origin", f"HEAD:{branch}"]' in text
    assert "--force" not in text
    assert '["gh", "workflow", "run", "ci.yml"' in text
    assert 'validation_env["DEVPILOT_RUN_BROWSER_E2E"] = "1"' in text
    assert "stale_failed_run" in text
    assert "pull_request_changes_control_plane" in text
