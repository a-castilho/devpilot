from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_ENTRY = (ROOT / "app/worker_entry.py").read_text(encoding="utf-8")
RECOVERY = (ROOT / "app/services/recovery.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "app/failure_recovery_routes.py").read_text(encoding="utf-8")
UI = (ROOT / "app/static/task-recovery-flow.js").read_text(encoding="utf-8")


def check() -> None:
    assert '"reading additional input from stdin"' in RECOVERY
    assert 'return "executor_runtime"' in RECOVERY
    assert 'strategy="retry_original_after_runner_fix"' in RECOVERY
    assert 'retry=False' in RECOVERY

    assert "def _invalidate_obsolete_platform_recoveries()" in WORKER_ENTRY
    assert 'action="failure_recovery.platform_obsoleted"' in WORKER_ENTRY
    assert 'state="canceled"' in WORKER_ENTRY
    assert WORKER_ENTRY.index("_invalidate_obsolete_platform_recoveries()") < WORKER_ENTRY.index("_recover_orphaned_running_tasks()", WORKER_ENTRY.index("def main()"))

    assert "EXECUTOR_STDIN_BLOCKED" in ROUTES
    assert '"action": "requeue_original"' in ROUTES
    assert "_requeue_platform_failure" in ROUTES

    assert "__devpilotTaskRecoveryFlowV104" in UI
    assert "platformStdinFailure" in UI
    assert "EXECUTOR_STDIN_BLOCKED" in UI
    assert "Recovery de projeto dispensada" in UI
    assert "Reexecutar tarefa no runner corrigido" in UI
    assert "async function retryPlatformTask" in UI
    assert "`/tasks/${encodeURIComponent(taskId)}/retry`" in UI
    assert "dataset.platformRecovery === '1'" in UI

    print("PLATFORM_STDIN_RECOVERY_V104=OK")


if __name__ == "__main__":
    check()
