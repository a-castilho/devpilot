import json
from types import SimpleNamespace

from app.models import TaskStatus
from app.services import failure_recovery
from app.task_run_routes import failure_details


def test_raw_github_failure_is_classified_for_automatic_recovery():
    run = SimpleNamespace(
        status="failed",
        logs=json.dumps({"stderr": "fatal: could not read Username for 'https://github.com': terminal prompts disabled"}),
        summary="GitHub clone failed",
    )

    details = failure_details(run)

    assert details["category"] == "github_auth"
    assert details["code"] == "GITHUB_ACCESS_DENIED"


def test_explicit_non_github_authorization_decision_remains_authoritative():
    run = SimpleNamespace(
        status="failed",
        logs=json.dumps(
            {
                "self_healing": {
                    "category": "filesystem_permission",
                    "message": "A permissão mínima precisa ser liberada externamente.",
                    "requires_authorization": True,
                }
            }
        ),
        summary="Execution failed",
    )

    details = failure_details(run)

    assert details["category"] == "filesystem_permission"
    assert details["requires_authorization"] is True


def test_existing_stale_github_recovery_gate_is_requeued_even_if_legacy_diagnosis_requested_authorization(monkeypatch):
    original = SimpleNamespace(
        id="task-original",
        workspace_id="workspace-1",
        project_id="project-1",
        status=TaskStatus.blocked,
    )
    recovery = SimpleNamespace(
        id="task-recovery",
        requires_approval=True,
        approved_at=None,
        status=TaskStatus.awaiting_approval,
        updated_at=None,
    )
    db = SimpleNamespace(flush=lambda: None)

    monkeypatch.setattr(failure_recovery, "find_failure_recovery_task", lambda _db, _task: recovery)
    monkeypatch.setattr(failure_recovery, "record", lambda *args, **kwargs: None)

    result = failure_recovery.ensure_failure_recovery_task(
        db,
        original_task=original,
        run=None,
        failure={
            "category": "github_auth",
            "code": "GITHUB_ACCESS_DENIED",
            "message": "Diagnóstico legado pediu revalidação manual do GitHub.",
            "requires_authorization": True,
        },
        actor="worker",
    )

    assert result is recovery
    assert recovery.requires_approval is False
    assert recovery.approved_at is not None
    assert recovery.status == TaskStatus.queued


def test_real_external_authorization_gate_is_not_bypassed(monkeypatch):
    original = SimpleNamespace(
        id="task-original",
        workspace_id="workspace-1",
        project_id="project-1",
        status=TaskStatus.blocked,
    )
    recovery = SimpleNamespace(
        id="task-recovery",
        requires_approval=True,
        approved_at=None,
        status=TaskStatus.awaiting_approval,
        updated_at=None,
    )
    db = SimpleNamespace(flush=lambda: None)

    monkeypatch.setattr(failure_recovery, "find_failure_recovery_task", lambda _db, _task: recovery)
    monkeypatch.setattr(failure_recovery, "record", lambda *args, **kwargs: None)

    failure_recovery.ensure_failure_recovery_task(
        db,
        original_task=original,
        run=None,
        failure={
            "category": "filesystem_permission",
            "code": "FILESYSTEM_PERMISSION_DENIED",
            "message": "Permissão externa realmente necessária.",
            "requires_authorization": True,
        },
        actor="worker",
    )

    assert recovery.requires_approval is True
    assert recovery.approved_at is None
    assert recovery.status == TaskStatus.awaiting_approval


def test_recovery_prompt_exhausts_automatic_alternatives_before_human_escalation():
    task = SimpleNamespace(id="task-1", title="Etapa 1", prompt="Objetivo original")
    prompt = failure_recovery.recovery_prompt(
        task,
        None,
        {
            "category": "github_auth",
            "code": "GITHUB_ACCESS_DENIED",
            "message": "Falha de acesso ao GitHub",
            "requires_authorization": True,
        },
    )

    normalized = prompt.casefold()
    assert "esgote" in normalized
    assert "alternativas automáticas" in normalized
    assert "última instância" in normalized
    assert "exige autorização externa: não" in normalized
