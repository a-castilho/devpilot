from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROVISION = ROOT / "app/project_provisioning_routes.py"
RECOVERY = ROOT / "app/failure_recovery_routes.py"


def test_missing_repository_recovery_provisions_before_resuming_original_task():
    provision = PROVISION.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")

    assert "def provision_repository_and_resume_task" in provision
    assert "provision_repository_in_background(project_id, workspace_id, actor)" in provision
    assert 'if task.status in {TaskStatus.failed, TaskStatus.blocked}' in provision
    assert "task.status = TaskStatus.queued" in provision
    assert 'action="project.repository_repair_resumed_task"' in provision

    assert '"category": "repository_not_ready"' in recovery
    assert '"code": "REPOSITORY_NOT_READY"' in recovery
    assert "queue_repository_repair(db, project" in recovery
    assert "background_tasks.add_task(" in recovery
    assert "provision_repository_and_resume_task" in recovery


def test_provider_failure_is_preserved_in_project_state_for_visible_diagnosis():
    provision = PROVISION.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")

    assert 'config["repository_provision_error"] = error_text[:2000]' in provision
    assert 'config["repository_provision_error"] = ""' in provision
    assert '"error": str(config.get("repository_provision_error") or "").strip()' in provision
    assert "provider_error = str(provision.get(\"error\") or \"\").strip()" in recovery
    assert "_authorization_error(provider_error)" in recovery


def test_old_failed_recovery_task_is_not_reused_for_empty_repository():
    recovery = RECOVERY.read_text(encoding="utf-8")
    assert '"recovery_task": None' in recovery
    assert "A recovery task antiga que também falhou por falta de checkout" in recovery
    assert "Reprovisionar o repositório GitHub do projeto" in recovery


def run_contract():
    test_missing_repository_recovery_provisions_before_resuming_original_task()
    test_provider_failure_is_preserved_in_project_state_for_visible_diagnosis()
    test_old_failed_recovery_task_is_not_reused_for_empty_repository()
    print("REPOSITORY_RECOVERY_V98=OK")


if __name__ == "__main__":
    run_contract()
