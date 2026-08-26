import hashlib
import hmac
from types import SimpleNamespace

from app.ci_routes import _verify_signature
from app.services.ci_orchestrator import CIFailure, failure_from_workflow_run


def workflow_payload(*, conclusion="failure", action="completed", attempt=1):
    return {
        "action": action,
        "repository": {"full_name": "a-castilho/devpilot"},
        "workflow_run": {
            "id": 12345,
            "name": "CI",
            "run_attempt": attempt,
            "head_sha": "abc123",
            "head_branch": "feat/example",
            "conclusion": conclusion,
            "html_url": "https://github.com/a-castilho/devpilot/actions/runs/12345",
        },
    }


def test_workflow_failure_becomes_actionable_ci_failure():
    failure = failure_from_workflow_run(workflow_payload())

    assert failure == CIFailure(
        repository_full_name="a-castilho/devpilot",
        workflow_name="CI",
        run_id=12345,
        run_attempt=1,
        head_sha="abc123",
        head_branch="feat/example",
        conclusion="failure",
        html_url="https://github.com/a-castilho/devpilot/actions/runs/12345",
    )
    assert failure.fingerprint_marker.startswith("[ci-failure:")
    assert failure.branch_marker == "[ci-branch:feat/example]"


def test_success_and_non_completed_events_are_ignored():
    assert failure_from_workflow_run(workflow_payload(conclusion="success")) is None
    assert failure_from_workflow_run(workflow_payload(action="requested")) is None


def test_rerun_attempt_changes_fingerprint_for_bounded_new_recovery():
    first = failure_from_workflow_run(workflow_payload(attempt=1))
    second = failure_from_workflow_run(workflow_payload(attempt=2))

    assert first is not None and second is not None
    assert first.fingerprint != second.fingerprint


def test_github_signature_requires_exact_sha256_hmac():
    body = b'{"action":"completed"}'
    secret = "unit-test-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert _verify_signature(body, f"sha256={digest}", secret) is True
    assert _verify_signature(body + b"x", f"sha256={digest}", secret) is False
    assert _verify_signature(body, "sha1=deadbeef", secret) is False
    assert _verify_signature(body, f"sha256={digest}", "") is False
