from pathlib import Path
from types import SimpleNamespace
import subprocess

from app.services.repair_pipeline import (
    REPAIR_PIPELINE_MARKER,
    finalize_repair_delivery,
    incident_block,
    incident_context,
)


class FakeExecutor:
    def __init__(self, repository: Path, responses: list[subprocess.CompletedProcess]):
        self.repository = repository
        self.responses = list(responses)
        self.commands = []

    def repository_path(self, project):
        return self.repository

    def git_environment(self, project):
        return {"GIT_TERMINAL_PROMPT": "0"}

    def run(self, args, cwd=None, timeout=900, env_overrides=None):
        self.commands.append(list(args))
        if not self.responses:
            raise AssertionError(f"unexpected command: {args}")
        return self.responses.pop(0)


def cp(args, rc=0, out="", err=""):
    return subprocess.CompletedProcess(args, rc, out, err)


def task():
    return SimpleNamespace(
        id="task-12345678",
        title="Corrigir login",
        prompt="Objetivo",
        project_id="project-1",
        branch_name="devpilot/repair-1234",
    )


def project():
    return SimpleNamespace(default_branch="main")


def run():
    return SimpleNamespace(id="run-1", commit_sha="", pull_request_url="", status="success", summary="ok")


def test_incident_context_is_compact_and_versioned():
    payload = incident_context(
        task=task(),
        run=run(),
        failure={
            "category": "repository_state",
            "code": "EXECUTION_FAILED",
            "message": "falha confirmada",
            "requires_authorization": False,
            "raw_secret": "must-not-be-copied",
        },
    )

    assert payload["version"] == 1
    assert payload["task_id"] == "task-12345678"
    assert payload["run_id"] == "run-1"
    assert payload["category"] == "repository_state"
    assert "raw_secret" not in payload

    block = incident_block(task=task(), run=run(), failure={"message": "falha"})
    assert REPAIR_PIPELINE_MARKER in block
    assert "repair-incident" in block


def test_environmental_repair_without_diff_is_ready_for_original_retest(tmp_path):
    executor = FakeExecutor(tmp_path, [cp(["git"], out="")])

    delivery = finalize_repair_delivery(
        executor_module=executor,
        project=project(),
        repair_task=task(),
        run=run(),
    )

    assert delivery.status == "no_changes"
    assert delivery.ci_status == "not_applicable"
    assert executor.commands == [["git", "status", "--porcelain"]]


def test_code_repair_creates_commit_pr_and_waits_for_ci(tmp_path):
    responses = [
        cp(["git"], out=" M app.py\n"),
        cp(["git"]),
        cp(["git"], rc=1),
        cp(["git"]),
        cp(["git"], out="abc123\n"),
        cp(["git"]),
        cp(["gh"], out="https://github.com/acme/project/pull/42\n"),
        cp(["gh"], out="CI pass\n"),
    ]
    executor = FakeExecutor(tmp_path, responses)

    delivery = finalize_repair_delivery(
        executor_module=executor,
        project=project(),
        repair_task=task(),
        run=run(),
    )

    assert delivery.status == "ready_to_retest"
    assert delivery.commit_sha == "abc123"
    assert delivery.pull_request_url == "https://github.com/acme/project/pull/42"
    assert delivery.ci_status == "passed"
    assert ["git", "push", "-u", "origin", "devpilot/repair-1234"] in executor.commands
    assert any(command[:3] == ["gh", "pr", "create"] for command in executor.commands)
    assert any(command[:3] == ["gh", "pr", "checks"] for command in executor.commands)


def test_failed_ci_blocks_original_retest(tmp_path):
    responses = [
        cp(["git"], out=" M app.py\n"),
        cp(["git"]),
        cp(["git"], rc=1),
        cp(["git"]),
        cp(["git"], out="abc123\n"),
        cp(["git"]),
        cp(["gh"], out="https://github.com/acme/project/pull/42\n"),
        cp(["gh"], rc=1, err="unit-tests failed"),
    ]
    executor = FakeExecutor(tmp_path, responses)

    delivery = finalize_repair_delivery(
        executor_module=executor,
        project=project(),
        repair_task=task(),
        run=run(),
    )

    assert delivery.status == "ci_failed"
    assert delivery.ci_status == "failed"
    assert "unit-tests failed" in delivery.message
